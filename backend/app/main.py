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

# 默认保持 SQLite，但可以通过环境变量覆盖为 mysql+pymysql://user:pass@host:port/db
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


# === 开始: 兼容 SQLite 和 MariaDB/MySQL ===
engine_kwargs = {}

# SQLite 需要 check_same_thread=False
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # MariaDB/MySQL 建议设置 pool_recycle 防止连接因为超时被数据库断开
    # 3600秒 (1小时) 回收一次连接
    engine_kwargs["pool_recycle"] = 3600
    # 如果需要调试 SQL 语句，可以开启 echo=True
    # engine_kwargs["echo"] = False

engine = create_engine(DATABASE_URL, **engine_kwargs)
# === 结束 ===



SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
scheduler = AsyncIOScheduler()

# ==========================================
# 2. 数据库模型
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    # MySQL 必须指定长度，例如 255
    username = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))

class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True, index=True)
    # 必须指定长度
    name = Column(String(255), unique=True, index=True)
    code = Column(Text) # Text 类型在 MySQL 中不需要长度
    requirements = Column(Text, default="")
    cron_exp = Column(String(100)) # 指定长度
    random_delay = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    last_run = Column(String(50), nullable=True)
    last_status = Column(String(50), nullable=True)
    last_log = Column(Text, default="[]")

class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, index=True)
    value = Column(Text) # 建议改为 Text 避免长度限制

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
# 5. 核心逻辑 (多语言支持)
# ==========================================

def detect_runtime(code: str) -> str:
    """检测代码语言: 'python' 或 'node'"""
    first_line = code.split('\n')[0].lower().strip()
    if "// runtime: node" in first_line or "#!nodejs" in first_line or "// language: javascript" in first_line:
        return "node"
    return "python"

async def prepare_env(script_id: int, requirements: str, runtime: str) -> tuple[str, str, float]:
    """根据运行时准备环境 (pip 或 npm)"""
    start_time = time.time()
    env_dir = os.path.join(VENVS_DIR, str(script_id))
    logs = []
    
    if not os.path.exists(env_dir):
        os.makedirs(env_dir, exist_ok=True)

    try:
        if runtime == "python":
            # --- Python Venv Logic ---
            python_exec = os.path.join(env_dir, "bin", "python")
            if not os.path.exists(python_exec):
                logs.append("Creating Python venv...")
                subprocess.run([sys.executable, "-m", "venv", env_dir], check=True)
            
            if requirements and requirements.strip():
                logs.append(f"Installing Python deps: {requirements}")
                req_file = os.path.join(env_dir, "requirements.txt")
                with open(req_file, "w") as f: f.write(requirements)
                # 使用清华源
                cmd = [os.path.join(env_dir, "bin", "pip"), "install", "-r", req_file, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if stdout: logs.append(stdout.decode())
                if stderr: logs.append(stderr.decode())
                if proc.returncode != 0: raise Exception("Pip install failed")
            return python_exec, "\n".join(logs), time.time() - start_time

        elif runtime == "node":
            # --- Node.js Logic ---
            # Node 不需要 venv，直接在目录里 npm install
            logs.append(f"Preparing Node.js environment at {env_dir}...")
            
            # 初始化 package.json 如果不存在
            pkg_file = os.path.join(env_dir, "package.json")
            if not os.path.exists(pkg_file):
                subprocess.run(["npm", "init", "-y"], cwd=env_dir, check=True, stdout=subprocess.DEVNULL)
            
            if requirements and requirements.strip():
                # 处理依赖字符串，支持换行或空格分隔
                deps = requirements.replace("\n", " ").split()
                deps = [d.strip() for d in deps if d.strip()]
                
                if deps:
                    logs.append(f"Installing Node deps: {', '.join(deps)}")
                    # npm install <packages>
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
    db = SessionLocal()
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script: return db.close()

    steps_log = []
    
    def update_db(status="Running"):
        script.last_log = json.dumps(steps_log)
        script.last_status = status
        script.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()

    logger.info(f"Task [{script.name}] started.")
    update_db("Running")

    # 0. Detect Runtime
    runtime = detect_runtime(script.code)
    logger.info(f"Task [{script.name}] detected runtime: {runtime}")

    # Step 1: Setup
    t0 = time.time()
    setup_log = f"Runner: GitHubActions-Universal\nRuntime: {runtime.upper()}\nTime: {datetime.now()}\n"
    
    delay = 0
    if override_delay >= 0: delay = override_delay
    elif script.random_delay > 0: delay = random.randint(0, script.random_delay)
    
    if delay > 0:
        setup_log += f"Anti-Bot: Sleeping {delay}s...\n"
        steps_log.append({"name": "Set up job", "status": 2, "duration": "...", "output": setup_log})
        update_db()
        await asyncio.sleep(delay)
    
    # 刷新 Step 1
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
        exec_cmd, out, dur = await prepare_env(script.id, script.requirements, runtime)
        steps_log.pop()
        steps_log.append({"name": "Install dependencies", "status": 0, "duration": f"{dur:.2f}s", "output": out})
        update_db()
    except Exception as e:
        steps_log.pop()
        steps_log.append({"name": "Install dependencies", "status": 1, "duration": f"{time.time()-t0:.2f}s", "output": str(e)})
        update_db("Failed")
        db.close()
        return

    # Step 3: Run Script
    t0 = time.time()
    steps_log.append({"name": "Run script", "status": 2, "duration": "...", "output": "Running..."})
    update_db()

    # 保存代码文件
    file_ext = ".js" if runtime == "node" else ".py"
    safe_name = "".join([c for c in script.name if c.isalnum() or c in (' ', '_', '-')]).strip()
    file_name = f"{safe_name}_{script.id}{file_ext}"
    file_path = os.path.join(SCRIPTS_DIR, file_name)
    
    with open(file_path, "w", encoding="utf-8") as f: f.write(script.code)
    
    # 注入环境变量
    env_vars = os.environ.copy()
    for s in db.query(Secret).all(): env_vars[s.key] = s.value
    
    internal_token = create_access_token({"sub": os.getenv("ADMIN_USER", "admin")})
    env_vars["FLUX_TOKEN"] = internal_token
    env_vars["FLUX_API_URL"] = "http://127.0.0.1:8000"
    env_vars["PYTHONUNBUFFERED"] = "1"
    
    # 如果是 Node，需要设置 NODE_PATH 以便能找到安装在 env_dir 下的包
    if runtime == "node":
        node_modules_path = os.path.join(env_dir, "node_modules")
        env_vars["NODE_PATH"] = node_modules_path
    
    try:
        # 构造启动命令
        if runtime == "node":
            # Node 脚本: node /app/scripts/xxx.js
            # 关键：cwd 要设置在 env_dir 才能正确加载 require() ? 
            # 不，我们通过 NODE_PATH 解决
            cmd_args = ["node", file_path]
        else:
            # Python 脚本: /app/data/venvs/1/bin/python /app/scripts/xxx.py
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

    # Step 4: Complete
    steps_log.append({"name": "Complete job", "status": 0, "duration": "0.1s", "output": "Done."})
    update_db(script.last_status)
    db.close()

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
    for col in ["requirements", "last_log"]:
        try: db.execute(text(f"SELECT {col} FROM scripts LIMIT 1"))
        except: 
            try: db.execute(text(f"ALTER TABLE scripts ADD COLUMN {col} TEXT DEFAULT ''")); db.commit()
            except: pass
    
    u = os.getenv("ADMIN_USER", "admin")
    p = os.getenv("ADMIN_PASSWORD", "admin")
    if not db.query(User).filter(User.username == u).first():
        db.add(User(username=u, hashed_password=pwd_context.hash(p))); db.commit()
    
    if not db.query(Secret).filter(Secret.key == "GITHUB_ACTIONS").first():
        db.add(Secret(key="GITHUB_ACTIONS", value="true")); db.commit()
    
    for s in db.query(Script).filter(Script.is_active == True).all(): add_job_to_scheduler(s)
    db.close()

@app.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not pwd_context.verify(form.password, user.hashed_password): raise HTTPException(status_code=400)
    return {"access_token": create_access_token({"sub": user.username}), "token_type": "bearer"}

@app.get("/api/scripts", response_model=List[ScriptResponse])
def get_scripts(db: Session = Depends(get_db), u=Depends(get_current_user)):
    scripts = db.query(Script).all()
    return [ScriptResponse(id=s.id, name=s.name, code=s.code, requirements=s.requirements, cron=s.cron_exp, delay=s.random_delay, last_run=s.last_run, last_status=s.last_status, last_log=s.last_log) for s in scripts]

@app.post("/api/scripts", response_model=ScriptResponse)
def create_script(s: ScriptBase, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if db.query(Script).filter(Script.name == s.name).first(): raise HTTPException(status_code=400, detail="Exists")
    new_s = Script(name=s.name, code=s.code, requirements=s.requirements, cron_exp=s.cron, random_delay=s.delay, last_log="[]")
    db.add(new_s); db.commit(); db.refresh(new_s); add_job_to_scheduler(new_s)
    return ScriptResponse(id=new_s.id, name=new_s.name, code=new_s.code, requirements=new_s.requirements, cron=new_s.cron_exp, delay=new_s.random_delay, last_run=new_s.last_run, last_status=new_s.last_status, last_log=new_s.last_log)

@app.put("/api/scripts/{script_id}", response_model=ScriptResponse)
def update_script(script_id: int, s: ScriptBase, db: Session = Depends(get_db), u=Depends(get_current_user)):
    item = db.query(Script).filter(Script.id == script_id).first()
    if not item: raise HTTPException(status_code=404)
    item.name = s.name; item.code = s.code; item.requirements = s.requirements; item.cron_exp = s.cron; item.random_delay = s.delay
    db.commit(); db.refresh(item); add_job_to_scheduler(item)
    return ScriptResponse(id=item.id, name=item.name, code=item.code, requirements=item.requirements, cron=item.cron_exp, delay=item.random_delay, last_run=item.last_run, last_status=item.last_status, last_log=item.last_log)

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

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(status_code=404)
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx): return FileResponse(idx)
    return {"message": "Frontend not found"}
