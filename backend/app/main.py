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

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    code = Column(Text)
    requirements = Column(Text, default="")
    cron_exp = Column(String)
    random_delay = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)
    last_status = Column(String, nullable=True)
    last_log = Column(Text, default="[]") 

class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)

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
# 5. 核心逻辑 (实时日志更新)
# ==========================================

async def prepare_venv(script_id: int, requirements: str) -> tuple[str, str, float]:
    start_time = time.time()
    venv_path = os.path.join(VENVS_DIR, str(script_id))
    python_exec = os.path.join(venv_path, "bin", "python")
    pip_exec = os.path.join(venv_path, "bin", "pip")
    logs = []

    try:
        if not os.path.exists(python_exec):
            logger.info(f"[{script_id}] Creating venv...")
            logs.append(f"Creating venv at {venv_path}...")
            subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
            logs.append("Venv created.")
        
        if requirements and requirements.strip():
            logger.info(f"[{script_id}] Installing requirements...")
            logs.append(f"Installing dependencies:\n{requirements}")
            req_file = os.path.join(venv_path, "requirements.txt")
            with open(req_file, "w") as f: f.write(requirements)
            cmd = [pip_exec, "install", "-r", req_file, "-i", "https://mirrors.aliyun.com/pypi/simple/"]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if stdout: logs.append(stdout.decode().strip())
            if stderr: logs.append(stderr.decode().strip())
            if proc.returncode != 0: raise Exception("Dependency install failed")
        else:
            logs.append("No requirements. Skipping pip install.")
            
    except Exception as e:
        logs.append(f"Error: {str(e)}")
        return python_exec, "\n".join(logs), time.time() - start_time

    return python_exec, "\n".join(logs), time.time() - start_time

async def run_script_task(script_id: int, override_delay: int = -1):
    db = SessionLocal()
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script: return db.close()

    steps_log = []
    total_start = time.time()
    
    # 辅助函数：实时更新数据库日志
    def update_db(status="Running"):
        script.last_log = json.dumps(steps_log)
        script.last_status = status
        script.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()

    logger.info(f"Task [{script.name}] started.")
    update_db("Running")

    # Step 1: Setup
    t0 = time.time()
    setup_log = f"Runner: github-actions-Worker\nTime: {datetime.now()}\n"
    delay = 0
    if override_delay >= 0: delay = override_delay
    elif script.random_delay > 0: delay = random.randint(0, script.random_delay)
    
    if delay > 0:
        logger.info(f"Task [{script.name}] waiting for {delay}s...")
        setup_log += f"Anti-Bot: Sleeping {delay}s...\n"
        # 记录正在等待
        steps_log.append({"name": "Set up job", "status": 2, "duration": "...", "output": setup_log}) # 2=Running
        update_db()
        await asyncio.sleep(delay)
    
    # 完成 Step 1
    steps_log = [s for s in steps_log if s["name"] != "Set up job"] # 移除旧的状态
    steps_log.append({"name": "Set up job", "status": 0, "duration": f"{time.time()-t0:.2f}s", "output": setup_log})
    update_db()

    # Step 2: Install Dependencies
    t0 = time.time()
    python_exec = "python3"
    # 记录开始安装
    steps_log.append({"name": "Install dependencies", "status": 2, "duration": "...", "output": "Installing..."})
    update_db()
    
    try:
        python_exec, out, dur = await prepare_venv(script.id, script.requirements)
        # 更新为完成
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
    logger.info(f"Task [{script.name}] executing...")
    # 记录开始运行
    steps_log.append({"name": "Run script", "status": 2, "duration": "...", "output": "Running..."})
    update_db()

    safe_name = "".join([c for c in script.name if c.isalnum() or c in (' ', '_', '-')]).strip()
    file_path = os.path.join(SCRIPTS_DIR, f"{safe_name}_{script.id}.py")
    with open(file_path, "w", encoding="utf-8") as f: f.write(script.code)
    
    env_vars = os.environ.copy()
    for s in db.query(Secret).all(): env_vars[s.key] = s.value
    env_vars["PYTHONUNBUFFERED"] = "1"
    
    try:
        proc = await asyncio.create_subprocess_exec(python_exec, file_path, env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    update_db(script.last_status) # 保持之前的状态
    
    logger.info(f"Task [{script.name}] finished.")
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

app = FastAPI(title="FluxTask")
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
    
    # 初始化管理员
    u = os.getenv("ADMIN_USER", "admin")
    p = os.getenv("ADMIN_PASSWORD", "admin")
    if not db.query(User).filter(User.username == u).first():
        db.add(User(username=u, hashed_password=pwd_context.hash(p))); db.commit()
    
    # --- 新增：初始化默认 GITHUB_ACTIONS 变量 ---
    if not db.query(Secret).filter(Secret.key == "GITHUB_ACTIONS").first():
        db.add(Secret(key="GITHUB_ACTIONS", value="true"))
        db.commit()
        logger.info("Initialized default secret: GITHUB_ACTIONS=true")
    
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
    db.delete(item)
    db.commit()
    return {"status": "deleted"}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(status_code=404)
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx): return FileResponse(idx)
    return {"message": "Frontend not found"}
