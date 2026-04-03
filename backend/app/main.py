import os
import sys
import signal
import random
import asyncio
import subprocess
import secrets
import shutil
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from passlib.context import CryptContext
from jose import JWTError, jwt
from loguru import logger

# ==========================================
# 1. 配置与初始化
# ==========================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/github-actions.db")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

SCRIPTS_DIR = "/app/scripts"
VENVS_DIR = "/app/data/venvs"
STATIC_DIR = "/app/static"
DATA_DIR = "/app/data"
SCRIPT_TIMEOUT_SECONDS = int(os.getenv("SCRIPT_TIMEOUT", "7200"))  # 默认 2 小时超时

# --- 修复#4: JWT Secret 持久化 ---
# 优先使用环境变量，否则从数据目录的隐藏文件中读取/生成，避免每次重启都变化
_SECRET_KEY_FILE = os.path.join(DATA_DIR, ".jwt_secret")

def _load_or_create_secret_key() -> str:
    env_key = os.getenv("JWT_SECRET")
    if env_key:
        return env_key
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(_SECRET_KEY_FILE):
        with open(_SECRET_KEY_FILE, "r") as f:
            key = f.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    with open(_SECRET_KEY_FILE, "w") as f:
        f.write(key)
    return key

SECRET_KEY = _load_or_create_secret_key()

os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(VENVS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_timeout"] = 30

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Shanghai"), job_defaults={'misfire_grace_time': 1800})

# ==========================================
# 2. 数据库模型
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))

class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    code = Column(Text)
    requirements = Column(Text, default="")
    cron_exp = Column(String(100))
    random_delay = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    last_run = Column(String(50), nullable=True)
    last_status = Column(String(50), nullable=True)
    last_log = Column(Text, default="[]")
    task_secrets = Column(Text, default="{}")
    req_hash = Column(String(64), default="")  # 修复#7: 依赖哈希，避免重复安装

class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, index=True)
    value = Column(Text)

Base.metadata.create_all(bind=engine)

# ==========================================
# 3. Pydantic 模型
# ==========================================

class ScriptBase(BaseModel):
    name: str
    code: str
    requirements: Optional[str] = ""
    cron: str
    delay: int = 0
    is_active: bool = True
    task_secrets: str = "{}"

class ScriptResponse(ScriptBase):
    id: int
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    last_log: Optional[str] = None
    class Config:
        from_attributes = True

class SecretCreate(BaseModel):
    key: str
    value: str

class SecretResponse(BaseModel):
    id: int
    key: str
    class Config:
        from_attributes = True

# ==========================================
# 4. 辅助函数
# ==========================================

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise HTTPException(status_code=401)
    except JWTError: raise HTTPException(status_code=401)
    user = db.query(User).filter(User.username == username).first()
    if user is None: raise HTTPException(status_code=401)
    return user

# --- 修复#5: 日志截断辅助函数 ---
LOG_MAX_LINES = 1000
LOG_MAX_CHARS = 200_000

def _truncate_log(text: str) -> str:
    """截断超长日志，只保留最后 LOG_MAX_LINES 行 / LOG_MAX_CHARS 字符"""
    if len(text) > LOG_MAX_CHARS:
        text = "...[日志过长，已截断前段输出]...\n" + text[-LOG_MAX_CHARS:]
    lines = text.splitlines()
    if len(lines) > LOG_MAX_LINES:
        lines = ["...[日志行数过多，已截断]..."] + lines[-LOG_MAX_LINES:]
        text = "\n".join(lines)
    return text

# ==========================================
# 5. 核心逻辑
# ==========================================

def detect_runtime(code: str) -> str:
    first_line = code.split('\n')[0].lower().strip()
    if "// runtime: node" in first_line or "#!nodejs" in first_line or "// language: javascript" in first_line:
        return "node"
    return "python"

def _req_hash(requirements: str) -> str:
    return hashlib.md5((requirements or "").strip().encode()).hexdigest()

async def prepare_env(script_id: int, requirements: str, runtime: str, current_hash: str = "") -> tuple[str, str, float]:
    """
    修复#2: 所有 subprocess.run 阻塞调用替换为 asyncio.create_subprocess_exec 或 asyncio.to_thread
    修复#7: 通过 requirements 哈希值避免每次都重复安装依赖
    """
    start_time = time.time()
    env_dir = os.path.join(VENVS_DIR, str(script_id))
    logs = []

    if not os.path.exists(env_dir):
        os.makedirs(env_dir, exist_ok=True)

    new_hash = _req_hash(requirements)
    hash_file = os.path.join(env_dir, ".req_hash")

    try:
        if runtime == "python":
            needs_playwright = requirements and "playwright" in requirements.lower()

            if needs_playwright:
                logs.append("Detected playwright dependency, using system Python (pre-installed)")
                logs.append("Skipping venv to reuse Docker's pre-installed browsers")

                other_deps = []
                for line in requirements.strip().split('\n'):
                    dep = line.strip().lower()
                    if dep and 'playwright' not in dep:
                        other_deps.append(line.strip())

                if other_deps:
                    logs.append(f"Installing additional deps: {', '.join(other_deps)}")
                    cmd = ["/usr/bin/pip3", "install", "--break-system-packages"] + other_deps + ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
                    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = await proc.communicate()
                    if stdout: logs.append(stdout.decode())
                    if stderr: logs.append(stderr.decode())
                    if proc.returncode != 0:
                        logs.append("Warning: Some deps may have failed, but continuing with system Python")

                return "/usr/bin/python3", "\n".join(logs), time.time() - start_time

            python_exec = os.path.join(env_dir, "bin", "python")
            if not os.path.exists(python_exec):
                logs.append("Creating Python venv...")
                # 修复#2: 使用 asyncio.to_thread 包装阻塞的 venv 创建调用
                await asyncio.to_thread(
                    lambda: subprocess.run([sys.executable, "-m", "venv", env_dir], check=True)
                )

            if requirements and requirements.strip():
                # 修复#7: 对比哈希，若依赖未变则跳过安装
                saved_hash = ""
                if os.path.exists(hash_file):
                    with open(hash_file, "r") as f:
                        saved_hash = f.read().strip()

                if saved_hash == new_hash:
                    logs.append(f"Dependencies unchanged (hash: {new_hash[:8]}...), skipping install.")
                else:
                    logs.append(f"Installing Python deps: {requirements}")
                    req_file = os.path.join(env_dir, "requirements.txt")
                    with open(req_file, "w") as f: f.write(requirements)
                    cmd = [os.path.join(env_dir, "bin", "pip"), "install", "-r", req_file, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
                    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = await proc.communicate()
                    if stdout: logs.append(stdout.decode())
                    if stderr: logs.append(stderr.decode())
                    if proc.returncode != 0: raise Exception("Pip install failed")
                    with open(hash_file, "w") as f: f.write(new_hash)

            return python_exec, "\n".join(logs), time.time() - start_time

        elif runtime == "node":
            logs.append(f"Preparing Node.js environment at {env_dir}...")
            pkg_file = os.path.join(env_dir, "package.json")
            if not os.path.exists(pkg_file):
                # 修复#2: 使用 asyncio.to_thread 包装阻塞的 npm init
                await asyncio.to_thread(
                    lambda: subprocess.run(["npm", "init", "-y"], cwd=env_dir, check=True, stdout=subprocess.DEVNULL)
                )

            if requirements and requirements.strip():
                req_str = requirements.strip()

                saved_hash = ""
                if os.path.exists(hash_file):
                    with open(hash_file, "r") as f:
                        saved_hash = f.read().strip()

                if saved_hash == new_hash:
                    logs.append(f"Dependencies unchanged (hash: {new_hash[:8]}...), skipping install.")
                    return "node", "\n".join(logs), time.time() - start_time

                if req_str.startswith("{"):
                    logs.append("Installing Node deps from package.json")
                    with open(pkg_file, "w") as f:
                        f.write(req_str)
                    cmd = ["npm", "install"]
                else:
                    deps = req_str.replace("\n", " ").split()
                    deps = [d.strip() for d in deps if d.strip()]
                    if deps:
                        logs.append(f"Installing Node deps: {', '.join(deps)}")
                        cmd = ["npm", "install"] + deps
                    else:
                        cmd = []

                if cmd:
                    proc = await asyncio.create_subprocess_exec(*cmd, cwd=env_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = await proc.communicate()
                    if stdout: logs.append(stdout.decode())
                    if stderr: logs.append(stderr.decode())
                    if proc.returncode != 0: raise Exception("Npm install failed")
                    with open(hash_file, "w") as f: f.write(new_hash)

            return "node", "\n".join(logs), time.time() - start_time

    except Exception as e:
        logs.append(f"Error: {str(e)}")
        raise Exception(f"Env setup failed: {e}")

    return "python", "Unknown runtime", 0

async def run_script_task(script_id: int, override_delay: int = -1):
    def get_script_data():
        db = SessionLocal()
        try:
            script = db.query(Script).filter(Script.id == script_id).first()
            if not script:
                return None
            return {
                "id": script.id,
                "name": script.name,
                "code": script.code,
                "requirements": script.requirements,
                "random_delay": script.random_delay,
                "task_secrets": script.task_secrets,
                "req_hash": script.req_hash or "",
            }
        finally:
            db.close()

    script_data = get_script_data()
    if not script_data:
        return

    steps_log = []

    def update_db(status="Running"):
        db = SessionLocal()
        try:
            script = db.query(Script).filter(Script.id == script_id).first()
            if script:
                # 修复#5: 序列化日志时对每个 step 的 output 进行截断
                truncated_steps = []
                for step in steps_log:
                    s = dict(step)
                    if isinstance(s.get("output"), str):
                        s["output"] = _truncate_log(s["output"])
                    truncated_steps.append(s)
                script.last_log = json.dumps(truncated_steps)
                script.last_status = status
                script.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update db for script {script_id}: {e}")
            db.rollback()
        finally:
            db.close()

    logger.info(f"Task [{script_data['name']}] started.")
    update_db("Running")

    runtime = detect_runtime(script_data['code'])

    # Step 1: Setup
    t0 = time.time()
    setup_log = f"Runner: GitHubActions-Universal\nRuntime: {runtime.upper()}\nTime: {datetime.now()}\n"

    delay = 0
    if override_delay >= 0: delay = override_delay
    elif script_data['random_delay'] > 0: delay = random.randint(0, script_data['random_delay'])

    if delay > 0:
        setup_log += f"Anti-Bot: Sleeping {delay}s...\n"
        steps_log.append({"name": "Set up job", "status": 2, "duration": "...", "output": setup_log})
        update_db()
        await asyncio.sleep(delay)

    steps_log = [s for s in steps_log if s["name"] != "Set up job"]
    steps_log.append({"name": "Set up job", "status": 0, "duration": f"{time.time()-t0:.2f}s", "output": setup_log})
    update_db()

    # Step 2: Check environment
    t0 = time.time()
    steps_log.append({"name": "Check environment", "status": 2, "duration": "...", "output": "Checking runtime environment..."})
    update_db()

    env_check_log = []
    if runtime == "python":
        env_check_log.append(f"Python version: {sys.version.split()[0]}")
        env_check_log.append(f"Platform: {sys.platform}")
    else:
        env_check_log.append("Node.js runtime")
    env_check_log.append(f"Working directory: {SCRIPTS_DIR}")
    env_check_log.append(f"Virtual env directory: {VENVS_DIR}")

    steps_log.pop()
    steps_log.append({"name": "Check environment", "status": 0, "duration": f"{time.time()-t0:.2f}s", "output": "\n".join(env_check_log)})
    update_db()

    # Step 3: Install Dependencies
    t0 = time.time()
    steps_log.append({"name": "Install dependencies", "status": 2, "duration": "...", "output": f"Installing {runtime} packages..."})
    update_db()

    exec_cmd = ""
    env_dir = os.path.join(VENVS_DIR, str(script_id))

    try:
        exec_cmd, out, dur = await prepare_env(script_data['id'], script_data['requirements'], runtime, script_data['req_hash'])
        steps_log.pop()
        steps_log.append({"name": "Install dependencies", "status": 0, "duration": f"{dur:.2f}s", "output": out})
        update_db()
    except Exception as e:
        steps_log.pop()
        steps_log.append({"name": "Install dependencies", "status": 1, "duration": f"{time.time()-t0:.2f}s", "output": str(e)})
        update_db("Failed")
        return

    # Step 4: Check browser (for Selenium/Playwright scripts)
    needs_browser = script_data['requirements'] and ('selenium' in script_data['requirements'].lower() or 'playwright' in script_data['requirements'].lower())
    if needs_browser:
        t0 = time.time()
        steps_log.append({"name": "Check browser", "status": 2, "duration": "...", "output": "Checking browser availability..."})
        update_db()

        browser_log = []
        chrome_bin = "/usr/bin/google-chrome"
        chromedriver = "/usr/bin/chromedriver"

        if os.path.exists(chrome_bin):
            try:
                result = subprocess.run([chrome_bin, "--version"], capture_output=True, text=True)
                browser_log.append(f"✓ Google Chrome: {result.stdout.strip()}")
            except:
                browser_log.append(f"✓ Google Chrome found: {chrome_bin}")
        else:
            browser_log.append(f"✗ Google Chrome not found at {chrome_bin}")

        if os.path.exists(chromedriver):
            try:
                result = subprocess.run([chromedriver, "--version"], capture_output=True, text=True)
                browser_log.append(f"✓ ChromeDriver: {result.stdout.strip()}")
            except:
                browser_log.append(f"✓ ChromeDriver found: {chromedriver}")
        else:
            browser_log.append(f"✗ ChromeDriver not found at {chromedriver}")

        xvfb_available = shutil.which("xvfb-run") is not None
        browser_log.append("✓ Xvfb virtual display: available" if xvfb_available else "⚠ Xvfb not found, using headless mode")
        browser_log.append("Environment: GitHub Actions compatible")

        steps_log.pop()
        steps_log.append({"name": "Check browser", "status": 0, "duration": f"{time.time()-t0:.2f}s", "output": "\n".join(browser_log)})
        update_db()

    # Step 5: Run Script
    t0 = time.time()
    steps_log.append({"name": "Run script", "status": 2, "duration": "...", "output": "Running..."})
    update_db()

    file_ext = ".js" if runtime == "node" else ".py"
    safe_name = "".join([c for c in script_data['name'] if c.isalnum() or c in (' ', '_', '-')]).strip()
    file_name = f"{safe_name}_{script_data['id']}{file_ext}"
    file_path = os.path.join(SCRIPTS_DIR, file_name)

    script_code = script_data['code']
    if runtime == "python":
        proxy_import = '''# === GitHub API Proxy (Auto-injected) ===
import sys, os
_proxy_path = "/app/app"
if _proxy_path not in sys.path: sys.path.insert(0, _proxy_path)
try:
    import github_api_proxy
except: pass
# === End Proxy ===

# === Selenium ChromeDriver Patch (Auto-injected) ===
def _patch_selenium_chrome():
    try:
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium import webdriver
        _original_chrome_init = webdriver.Chrome.__init__
        def _patched_chrome_init(self, options=None, service=None, keep_alive=True):
            if service is None:
                chromedriver_path = os.getenv("CHROMEDRIVER", "/usr/bin/chromedriver")
                if os.path.exists(chromedriver_path):
                    service = Service(executable_path=chromedriver_path)
            if options is None:
                options = Options()
            chrome_bin = os.getenv("CHROME_BIN", "/usr/bin/google-chrome")
            if os.path.exists(chrome_bin):
                options.binary_location = chrome_bin
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            if not os.getenv("DISPLAY"):
                options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            return _original_chrome_init(self, options=options, service=service, keep_alive=keep_alive)
        webdriver.Chrome.__init__ = _patched_chrome_init
    except Exception:
        pass
_patch_selenium_chrome()
# === End Selenium Patch ===

'''
        script_code = proxy_import + script_code

    with open(file_path, "w", encoding="utf-8") as f: f.write(script_code)

    env_vars = os.environ.copy()
    db_secrets = SessionLocal()
    try:
        for s in db_secrets.query(Secret).all(): env_vars[s.key] = s.value
    finally:
        db_secrets.close()
    try:
        task_specific_secrets = json.loads(script_data['task_secrets'])
        if isinstance(task_specific_secrets, dict):
            for k, v in task_specific_secrets.items():
                env_vars[k] = str(v)
    except Exception as e:
        logger.error(f"Failed to parse task_secrets for script {script_data['id']}: {e}")

    internal_token = create_access_token({"sub": os.getenv("ADMIN_USER", "admin")})
    env_vars["FLUX_TOKEN"] = internal_token
    env_vars["FLUX_API_URL"] = "http://127.0.0.1:8000"
    env_vars["FLUX_SCRIPT_ID"] = str(script_data['id'])
    env_vars["PYTHONUNBUFFERED"] = "1"
    env_vars["GITHUB_ACTIONS"] = "true"
    env_vars["CHROME_BIN"] = "/usr/bin/google-chrome"
    env_vars["CHROMEDRIVER"] = "/usr/bin/chromedriver"
    env_vars["DISPLAY"] = ":99"
    env_vars["WDM_LOCAL"] = "1"
    env_vars["WDM_SSL_VERIFY"] = "0"
    env_vars["SE_AVOID_STATS"] = "true"

    if runtime == "node":
        node_modules_path = os.path.join(env_dir, "node_modules")
        env_vars["NODE_PATH"] = node_modules_path

    try:
        use_xvfb = needs_browser and shutil.which("xvfb-run") is not None

        if runtime == "node":
            if use_xvfb:
                cmd_args = ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "node", file_path]
            else:
                cmd_args = ["node", file_path]
        else:
            if use_xvfb:
                cmd_args = ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", exec_cmd, file_path]
            else:
                cmd_args = [exec_cmd, file_path]

        # 修复#1: 使用 start_new_session=True 让子进程独立成进程组，便于超时时整组杀掉
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True   # 关键：分配独立进程组
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=SCRIPT_TIMEOUT_SECONDS
            )
            output = _truncate_log(stdout.decode().strip() + "\n" + stderr.decode().strip())
            steps_log.pop()
            steps_log.append({"name": "Run script", "status": 0 if proc.returncode == 0 else 1, "duration": f"{time.time()-t0:.2f}s", "output": output})
            update_db("Success" if proc.returncode == 0 else "Failed")
        except asyncio.TimeoutError:
            # 修复#1: 超时时通过 os.killpg 杀掉整个进程组（含浏览器子进程）
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                await asyncio.sleep(3)
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            steps_log.pop()
            steps_log.append({"name": "Run script", "status": 1, "duration": f"{time.time()-t0:.2f}s", "output": f"Script execution timed out after {SCRIPT_TIMEOUT_SECONDS}s"})
            update_db("Timeout")
    except Exception as e:
        steps_log.pop()
        steps_log.append({"name": "Run script", "status": 1, "duration": f"{time.time()-t0:.2f}s", "output": str(e)})
        update_db("Error")

    steps_log.append({"name": "Complete job", "status": 0, "duration": "0.1s", "output": "Done."})

def add_job_to_scheduler(script: Script):
    try: scheduler.remove_job(str(script.id))
    except: pass
    if not script.is_active: return
    try:
        parts = script.cron_exp.strip().split()
        if len(parts) != 5: return
        scheduler.add_job(run_script_task, CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]), id=str(script.id), args=[script.id], replace_existing=True)
    except: pass

# ==========================================
# 6. API 路由
# ==========================================

app = FastAPI(title="GitHubActions")
app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

@app.on_event("startup")
def startup_event():
    scheduler.start()
    db = SessionLocal()

    # 自动迁移：检查并添加新列
    for col in ["requirements", "last_log", "task_secrets", "is_active", "req_hash"]:
        try: db.execute(text(f"SELECT {col} FROM scripts LIMIT 1"))
        except:
            try:
                db.execute(text(f"ALTER TABLE scripts ADD COLUMN {col} TEXT DEFAULT ''"))
                db.commit()
            except Exception as e: logger.error(f"Migration error for {col}: {e}")

    # 修复#3: 启动时将所有 Running 状态的任务置为 Failed (Killed)，避免重启后永久卡住
    try:
        stale_count = db.query(Script).filter(Script.last_status == "Running").update(
            {"last_status": "Failed (Killed)"},
            synchronize_session=False
        )
        if stale_count:
            logger.warning(f"Startup: reset {stale_count} stale 'Running' task(s) to 'Failed (Killed)'")
        db.commit()
    except Exception as e:
        logger.error(f"Startup stale task cleanup error: {e}")
        db.rollback()

    u = os.getenv("ADMIN_USER", "admin")
    p = os.getenv("ADMIN_PASSWORD", "admin")
    if not db.query(User).filter(User.username == u).first():
        db.add(User(username=u, hashed_password=pwd_context.hash(p))); db.commit()

    if not db.query(Secret).filter(Secret.key == "GITHUB_ACTIONS").first():
        db.add(Secret(key="GITHUB_ACTIONS", value="true")); db.commit()

    for s in db.query(Script).filter(Script.is_active == True).all(): add_job_to_scheduler(s)

    logger.info(f"Scheduler initialized with timezone: {scheduler.timezone}")
    logger.info(f"Scheduler running: {scheduler.running}")

    db.close()

@app.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not pwd_context.verify(form.password, user.hashed_password): raise HTTPException(status_code=400)
    return {"access_token": create_access_token({"sub": user.username}), "token_type": "bearer"}

@app.get("/api/scripts", response_model=List[ScriptResponse])
def get_scripts(db: Session = Depends(get_db), u=Depends(get_current_user)):
    scripts = db.query(Script).all()
    return [ScriptResponse(
        id=s.id, name=s.name, code=s.code, requirements=s.requirements,
        cron=s.cron_exp, delay=s.random_delay, is_active=s.is_active,
        last_run=s.last_run, last_status=s.last_status, last_log=s.last_log,
        task_secrets=s.task_secrets
    ) for s in scripts]

@app.post("/api/scripts", response_model=ScriptResponse)
def create_script(s: ScriptBase, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if db.query(Script).filter(Script.name == s.name).first(): raise HTTPException(status_code=400, detail="Exists")
    new_s = Script(
        name=s.name, code=s.code, requirements=s.requirements,
        cron_exp=s.cron, random_delay=s.delay, is_active=s.is_active,
        task_secrets=s.task_secrets,
        req_hash="",
        last_log="[]"
    )
    db.add(new_s); db.commit(); db.refresh(new_s); add_job_to_scheduler(new_s)
    return ScriptResponse(
        id=new_s.id, name=new_s.name, code=new_s.code, requirements=new_s.requirements,
        cron=new_s.cron_exp, delay=new_s.random_delay, is_active=new_s.is_active,
        task_secrets=new_s.task_secrets,
        last_run=new_s.last_run, last_status=new_s.last_status, last_log=new_s.last_log
    )

@app.put("/api/scripts/{script_id}", response_model=ScriptResponse)
def update_script(script_id: int, s: ScriptBase, db: Session = Depends(get_db), u=Depends(get_current_user)):
    item = db.query(Script).filter(Script.id == script_id).first()
    if not item: raise HTTPException(status_code=404)

    item.name = s.name
    item.code = s.code
    # 修复#7: 若 requirements 内容变更，清空哈希以强制下次重装
    if (item.requirements or "") != (s.requirements or ""):
        item.req_hash = ""
    item.requirements = s.requirements
    item.cron_exp = s.cron
    item.random_delay = s.delay
    item.is_active = s.is_active
    item.task_secrets = s.task_secrets

    db.commit(); db.refresh(item); add_job_to_scheduler(item)
    return ScriptResponse(
        id=item.id, name=item.name, code=item.code, requirements=item.requirements,
        cron=item.cron_exp, delay=item.random_delay, is_active=item.is_active,
        task_secrets=item.task_secrets,
        last_run=item.last_run, last_status=item.last_status, last_log=item.last_log
    )

@app.delete("/api/scripts/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    item = db.query(Script).filter(Script.id == script_id).first()
    if not item: raise HTTPException(status_code=404)
    try: scheduler.remove_job(str(script_id))
    except: pass
    if os.path.exists(os.path.join(VENVS_DIR, str(script_id))): shutil.rmtree(os.path.join(VENVS_DIR, str(script_id)), ignore_errors=True)
    db.delete(item); db.commit()
    return {"status": "deleted"}

@app.post("/api/scripts/{script_id}/run")
async def run_now(script_id: int, u=Depends(get_current_user)):
    asyncio.create_task(run_script_task(script_id, 0)); return {"status": "triggered"}

@app.post("/api/scripts/{script_id}/cancel")
def cancel_script(script_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """手动将卡住的任务状态重置为 Cancelled"""
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404)
    if script.last_status == "Running":
        script.last_status = "Cancelled"
        db.commit()
    return {"status": "cancelled"}

@app.get("/api/secrets", response_model=List[SecretResponse])
def get_secrets(db: Session = Depends(get_db), u=Depends(get_current_user)):
    return db.query(Secret).all()

@app.post("/api/secrets")
def save_secret(s: SecretCreate, db: Session = Depends(get_db), u=Depends(get_current_user)):
    exist = db.query(Secret).filter(Secret.key == s.key).first()
    if exist:
        exist.value = s.value; db.commit(); return {"id": exist.id, "key": exist.key}
    new_s = Secret(key=s.key, value=s.value); db.add(new_s); db.commit(); db.refresh(new_s)
    return {"id": new_s.id, "key": new_s.key}

@app.delete("/api/secrets/{secret_id}")
def delete_secret(secret_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    item = db.query(Secret).filter(Secret.id == secret_id).first()
    if not item: raise HTTPException(status_code=404, detail="Secret not found")
    db.delete(item); db.commit()
    return {"status": "deleted"}

@app.put("/api/secrets/{key}")
def update_secret_by_key(key: str, value: str = Body(..., embed=True), db: Session = Depends(get_db), u=Depends(get_current_user)):
    """允许脚本通过 API 更新 Secret 值"""
    exist = db.query(Secret).filter(Secret.key == key).first()
    if not exist:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found")
    exist.value = value
    db.commit()
    return {"status": "updated", "key": key}

@app.put("/api/scripts/{script_id}/secrets/{key}")
def update_task_secret(script_id: int, key: str, value: str = Body(..., embed=True), db: Session = Depends(get_db), u=Depends(get_current_user)):
    """更新任务独享的 Secrets"""
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    try:
        secrets_dict = json.loads(script.task_secrets or "{}")
    except:
        secrets_dict = {}
    secrets_dict[key] = value
    script.task_secrets = json.dumps(secrets_dict)
    db.commit()
    return {"status": "updated", "script_id": script_id, "key": key}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(status_code=404)
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx): return FileResponse(idx)
    return {"message": "Frontend not found"}
