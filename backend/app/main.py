import os
import sys
import random
import asyncio
import subprocess
import secrets
import shutil
import json
import time
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

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
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

SCRIPTS_DIR = "/app/scripts"
VENVS_DIR = "/app/data/venvs"
STATIC_DIR = "/app/static"

os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(VENVS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # 外挂数据库（MariaDB/MySQL）连接池配置
    engine_kwargs["pool_recycle"] = 300  # 5分钟回收连接（避免云数据库超时）
    engine_kwargs["pool_pre_ping"] = True  # 使用前检测连接是否有效
    engine_kwargs["pool_size"] = 5  # 连接池大小
    engine_kwargs["max_overflow"] = 10  # 允许的额外连接数
    engine_kwargs["pool_timeout"] = 30  # 获取连接超时

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
    is_active = Column(Boolean, default=True) # 用于暂停/恢复
    last_run = Column(String(50), nullable=True)
    last_status = Column(String(50), nullable=True)
    last_log = Column(Text, default="[]")
    task_secrets = Column(Text, default="{}") # 新增：任务独享 Secrets (JSON格式)

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
    is_active: bool = True # 允许前端控制激活状态
    task_secrets: str = "{}" # 传递 JSON 字符串

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

# ==========================================
# 5. 核心逻辑
# ==========================================

def detect_runtime(code: str) -> str:
    first_line = code.split('\n')[0].lower().strip()
    if "// runtime: node" in first_line or "#!nodejs" in first_line or "// language: javascript" in first_line:
        return "node"
    return "python"

async def prepare_env(script_id: int, requirements: str, runtime: str) -> tuple[str, str, float]:
    start_time = time.time()
    env_dir = os.path.join(VENVS_DIR, str(script_id))
    logs = []
    
    if not os.path.exists(env_dir):
        os.makedirs(env_dir, exist_ok=True)

    try:
        if runtime == "python":
            # 检测是否需要 playwright（使用系统级 Python，复用 Docker 预装的浏览器）
            needs_playwright = requirements and "playwright" in requirements.lower()
            
            if needs_playwright:
                logs.append("Detected playwright dependency, using system Python (pre-installed)")
                logs.append("Skipping venv creation to reuse Docker's pre-installed browsers")
                return "/usr/bin/python3", "\n".join(logs), time.time() - start_time
            
            # 其他任务继续使用 venv 隔离
            python_exec = os.path.join(env_dir, "bin", "python")
            if not os.path.exists(python_exec):
                logs.append("Creating Python venv...")
                subprocess.run([sys.executable, "-m", "venv", env_dir], check=True)
            
            if requirements and requirements.strip():
                logs.append(f"Installing Python deps: {requirements}")
                req_file = os.path.join(env_dir, "requirements.txt")
                with open(req_file, "w") as f: f.write(requirements)
                cmd = [os.path.join(env_dir, "bin", "pip"), "install", "-r", req_file, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if stdout: logs.append(stdout.decode())
                if stderr: logs.append(stderr.decode())
                if proc.returncode != 0: raise Exception("Pip install failed")
            return python_exec, "\n".join(logs), time.time() - start_time

        elif runtime == "node":
            logs.append(f"Preparing Node.js environment at {env_dir}...")
            pkg_file = os.path.join(env_dir, "package.json")
            if not os.path.exists(pkg_file):
                subprocess.run(["npm", "init", "-y"], cwd=env_dir, check=True, stdout=subprocess.DEVNULL)
            
            if requirements and requirements.strip():
                deps = requirements.replace("\n", " ").split()
                deps = [d.strip() for d in deps if d.strip()]
                if deps:
                    logs.append(f"Installing Node deps: {', '.join(deps)}")
                    cmd = ["npm", "install"] + deps
                    proc = await asyncio.create_subprocess_exec(*cmd, cwd=env_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = await proc.communicate()
                    if stdout: logs.append(stdout.decode())
                    if stderr: logs.append(stderr.decode())
                    if proc.returncode != 0: raise Exception("Npm install failed")
            return "node", "\n".join(logs), time.time() - start_time

    except Exception as e:
        logs.append(f"Error: {str(e)}")
        raise Exception(f"Env setup failed: {e}")

    return "python", "Unknown runtime", 0

async def run_script_task(script_id: int, override_delay: int = -1):
    # 使用短连接模式：每次操作后关闭连接，避免外挂数据库超时
    def get_script_data():
        db = SessionLocal()
        try:
            script = db.query(Script).filter(Script.id == script_id).first()
            if not script:
                return None
            # 返回需要的数据副本
            return {
                "id": script.id,
                "name": script.name,
                "code": script.code,
                "requirements": script.requirements,
                "random_delay": script.random_delay,
                "task_secrets": script.task_secrets,
            }
        finally:
            db.close()
    
    script_data = get_script_data()
    if not script_data:
        return

    steps_log = []
    
    def update_db(status="Running"):
        """使用新连接更新数据库，避免长连接超时"""
        db = SessionLocal()
        try:
            script = db.query(Script).filter(Script.id == script_id).first()
            if script:
                script.last_log = json.dumps(steps_log)
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

    # Step 2: Install Dependencies
    t0 = time.time()
    steps_log.append({"name": "Install dependencies", "status": 2, "duration": "...", "output": f"Installing {runtime} packages..."})
    update_db()
    
    exec_cmd = ""
    env_dir = os.path.join(VENVS_DIR, str(script_id))
    
    try:
        exec_cmd, out, dur = await prepare_env(script_data['id'], script_data['requirements'], runtime)
        steps_log.pop()
        steps_log.append({"name": "Install dependencies", "status": 0, "duration": f"{dur:.2f}s", "output": out})
        update_db()
    except Exception as e:
        steps_log.pop()
        steps_log.append({"name": "Install dependencies", "status": 1, "duration": f"{time.time()-t0:.2f}s", "output": str(e)})
        update_db("Failed")
        return

    # Step 3: Run Script
    t0 = time.time()
    steps_log.append({"name": "Run script", "status": 2, "duration": "...", "output": "Running..."})
    update_db()

    file_ext = ".js" if runtime == "node" else ".py"
    safe_name = "".join([c for c in script_data['name'] if c.isalnum() or c in (' ', '_', '-')]).strip()
    file_name = f"{safe_name}_{script_data['id']}{file_ext}"
    file_path = os.path.join(SCRIPTS_DIR, file_name)
    
    # 为 Python 脚本注入 GitHub API 代理模块
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

'''
        script_code = proxy_import + script_code
    
    with open(file_path, "w", encoding="utf-8") as f: f.write(script_code)
    
    # 注入环境变量
    env_vars = os.environ.copy()
    # 1. 注入全局 Secrets（使用短连接）
    db_secrets = SessionLocal()
    try:
        for s in db_secrets.query(Secret).all(): env_vars[s.key] = s.value
    finally:
        db_secrets.close()
    # 2. 注入任务独享 Secrets (覆盖全局)
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
    env_vars["FLUX_SCRIPT_ID"] = str(script_data['id'])  # 注入脚本ID供更新任务Secrets使用
    env_vars["PYTHONUNBUFFERED"] = "1"
    env_vars["GITHUB_ACTIONS"] = "true" # 模拟 GitHub Actions 环境
    
    if runtime == "node":
        node_modules_path = os.path.join(env_dir, "node_modules")
        env_vars["NODE_PATH"] = node_modules_path
    
    try:
        if runtime == "node":
            cmd_args = ["node", file_path]
        else:
            cmd_args = [exec_cmd, file_path]

        proc = await asyncio.create_subprocess_exec(
            *cmd_args, 
            env=env_vars, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        steps_log.pop()
        steps_log.append({"name": "Run script", "status": 0 if proc.returncode==0 else 1, "duration": f"{time.time()-t0:.2f}s", "output": stdout.decode().strip() + "\n" + stderr.decode().strip()})
        update_db("Success" if proc.returncode == 0 else "Failed")
    except Exception as e:
        steps_log.pop()
        steps_log.append({"name": "Run script", "status": 1, "duration": f"{time.time()-t0:.2f}s", "output": str(e)})
        update_db("Error")

    steps_log.append({"name": "Complete job", "status": 0, "duration": "0.1s", "output": "Done."})

def add_job_to_scheduler(script: Script):
    try: scheduler.remove_job(str(script.id))
    except: pass
    if not script.is_active: return # 如果未激活(暂停)，不添加到调度器
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
    for col in ["requirements", "last_log", "task_secrets", "is_active"]:
        try: db.execute(text(f"SELECT {col} FROM scripts LIMIT 1"))
        except: 
            try: 
                # SQLite 和 MySQL 的列添加语法略有不同，这里做一个简单的兼容
                # 实际上 SQLAlchemy 最好用 Alembic，这里为了单文件简便处理
                db.execute(text(f"ALTER TABLE scripts ADD COLUMN {col} TEXT DEFAULT ''"))
                db.commit()
            except Exception as e: logger.error(f"Migration error for {col}: {e}")
    
    u = os.getenv("ADMIN_USER", "admin")
    p = os.getenv("ADMIN_PASSWORD", "admin")
    if not db.query(User).filter(User.username == u).first():
        db.add(User(username=u, hashed_password=pwd_context.hash(p))); db.commit()
    
    if not db.query(Secret).filter(Secret.key == "GITHUB_ACTIONS").first():
        db.add(Secret(key="GITHUB_ACTIONS", value="true")); db.commit()
    
    for s in db.query(Script).filter(Script.is_active == True).all(): add_job_to_scheduler(s)
    
    # 打印调度器信息，确认时区
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
    # 确保返回所有字段
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
    item.requirements = s.requirements
    item.cron_exp = s.cron
    item.random_delay = s.delay
    item.is_active = s.is_active # 更新激活状态
    item.task_secrets = s.task_secrets # 更新任务 Secrets
    
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
    """允许脚本通过 API 更新 Secret 值（用于 REPO_TOKEN 功能）"""
    exist = db.query(Secret).filter(Secret.key == key).first()
    if not exist:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found")
    exist.value = value
    db.commit()
    return {"status": "updated", "key": key}

@app.put("/api/scripts/{script_id}/secrets/{key}")
def update_task_secret(script_id: int, key: str, value: str = Body(..., embed=True), db: Session = Depends(get_db), u=Depends(get_current_user)):
    """更新任务独享的 Secrets（脚本使用 FLUX_SCRIPT_ID 调用）"""
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    
    # 解析现有的 task_secrets
    try:
        secrets_dict = json.loads(script.task_secrets or "{}")
    except:
        secrets_dict = {}
    
    # 更新或新增指定的 key
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
