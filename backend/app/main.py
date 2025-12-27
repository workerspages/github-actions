import os
import sys
import random
import asyncio
import subprocess
import secrets
import shutil
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

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/fluxtask.db")
# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 目录配置
SCRIPTS_DIR = "/app/scripts"
VENVS_DIR = "/app/data/venvs"  # 虚拟环境目录
STATIC_DIR = "/app/static"

os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(VENVS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# 数据库引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 认证工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 调度器
scheduler = AsyncIOScheduler()

# ==========================================
# 2. 数据库模型 (Models)
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
    code = Column(Text)              # Python 代码
    requirements = Column(Text, default="") # 依赖列表
    cron_exp = Column(String)        # 数据库字段名: cron_exp
    random_delay = Column(Integer, default=0) # 数据库字段名: random_delay
    is_active = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)
    last_status = Column(String, nullable=True)

class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)

# 创建表结构
Base.metadata.create_all(bind=engine)

# ==========================================
# 3. Pydantic 数据校验模型
# ==========================================

class ScriptBase(BaseModel):
    name: str
    code: str
    requirements: Optional[str] = ""
    cron: str  # 前端字段名: cron
    delay: int = 0 # 前端字段名: delay

class ScriptResponse(ScriptBase):
    id: int
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    
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
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise HTTPException(status_code=401)
    except JWTError:
        raise HTTPException(status_code=401)
    
    user = db.query(User).filter(User.username == username).first()
    if user is None: raise HTTPException(status_code=401)
    return user

# ==========================================
# 5. 核心逻辑：虚拟环境与执行
# ==========================================

async def prepare_venv(script_id: int, requirements: str) -> str:
    """
    为脚本创建/更新虚拟环境，并返回该环境的 python 可执行文件路径。
    """
    venv_path = os.path.join(VENVS_DIR, str(script_id))
    python_exec = os.path.join(venv_path, "bin", "python")
    pip_exec = os.path.join(venv_path, "bin", "pip")

    # 1. 检查虚拟环境是否存在，不存在则创建
    if not os.path.exists(python_exec):
        logger.info(f"Creating venv for script {script_id}...")
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
    
    # 2. 安装依赖
    if requirements and requirements.strip():
        req_file = os.path.join(venv_path, "requirements.txt")
        with open(req_file, "w") as f:
            f.write(requirements)
        
        logger.info(f"Installing dependencies for script {script_id}...")
        # 使用阿里云镜像加速
        cmd = [
            pip_exec, "install", "-r", req_file,
            "-i", "https://mirrors.aliyun.com/pypi/simple/"
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error(f"Pip install failed: {stderr.decode()}")
            raise Exception(f"Dependency installation failed: {stderr.decode()}")
            
    return python_exec

async def run_script_task(script_id: int, override_delay: int = -1):
    """执行脚本任务"""
    db = SessionLocal()
    try:
        script = db.query(Script).filter(Script.id == script_id).first()
        if not script: return

        # 1. 随机延时
        delay = 0
        if override_delay >= 0:
            delay = override_delay
        elif script.random_delay > 0:
            delay = random.randint(0, script.random_delay)
        
        if delay > 0:
            logger.info(f"Task [{script.name}] sleeping for {delay}s...")
            await asyncio.sleep(delay)

        # 2. 准备代码文件
        safe_name = "".join([c for c in script.name if c.isalnum() or c in (' ', '_', '-')]).strip()
        file_path = os.path.join(SCRIPTS_DIR, f"{safe_name}_{script.id}.py")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script.code)

        # 3. 准备 Python 环境
        python_executable = "python3" # 默认系统Python
        
        if script.requirements and script.requirements.strip():
            try:
                python_executable = await prepare_venv(script.id, script.requirements)
            except Exception as e:
                logger.error(f"Venv Error for {script.name}: {e}")
                script.last_status = "Dep Error"
                db.commit()
                return

        # 4. 环境变量注入
        env_vars = os.environ.copy()
        for s in db.query(Secret).all():
            env_vars[s.key] = s.value
        env_vars["PYTHONUNBUFFERED"] = "1"

        logger.info(f"Executing [{script.name}] using [{python_executable}]")
        
        # 5. 执行脚本
        process = await asyncio.create_subprocess_exec(
            python_executable, file_path,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # 6. 更新状态
        script.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stdout_str = stdout.decode().strip()
        stderr_str = stderr.decode().strip()

        if process.returncode == 0:
            script.last_status = "Success"
            logger.info(f"[{script.name}] OK.\n{stdout_str}")
        else:
            script.last_status = "Failed"
            logger.error(f"[{script.name}] FAIL.\nErr: {stderr_str}\nOut: {stdout_str}")
        
        db.commit()

    except Exception as e:
        logger.error(f"System Error task {script_id}: {e}")
        try:
            if 'script' in locals() and script:
                script.last_status = "Error"
                db.commit()
        except: pass
    finally:
        db.close()

def add_job_to_scheduler(script: Script):
    try:
        scheduler.remove_job(str(script.id))
    except: pass

    if not script.is_active: return

    try:
        parts = script.cron_exp.strip().split()
        if len(parts) != 5: return
        scheduler.add_job(
            run_script_task,
            CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]),
            id=str(script.id), args=[script.id], replace_existing=True
        )
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
    
    # --- 数据库自动修复: 添加 requirements 列 ---
    try:
        db.execute(text("SELECT requirements FROM scripts LIMIT 1"))
    except Exception:
        logger.warning("Auto-migrating database: adding 'requirements' column...")
        try:
            db.execute(text("ALTER TABLE scripts ADD COLUMN requirements TEXT DEFAULT ''"))
            db.commit()
            logger.info("Migration successful.")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
    
    # --- 管理员账户初始化 ---
    u = os.getenv("ADMIN_USER", "admin")
    p = os.getenv("ADMIN_PASSWORD", "admin")
    if not db.query(User).filter(User.username == u).first():
        db.add(User(username=u, hashed_password=pwd_context.hash(p)))
        db.commit()
        logger.info(f"Created admin: {u}")
    
    # --- 加载任务 ---
    try:
        for s in db.query(Script).filter(Script.is_active == True).all():
            add_job_to_scheduler(s)
    except Exception as e:
        logger.error(f"Error loading scripts: {e}")
        
    db.close()

@app.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not pwd_context.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": create_access_token({"sub": user.username}), "token_type": "bearer"}

# --- 关键修改：手动映射字段以解决 Pydantic 验证错误 ---

@app.get("/api/scripts", response_model=List[ScriptResponse])
def get_scripts(db: Session = Depends(get_db), u=Depends(get_current_user)):
    scripts = db.query(Script).all()
    # 手动构建响应列表，映射 cron_exp -> cron, random_delay -> delay
    return [
        ScriptResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            requirements=s.requirements,
            cron=s.cron_exp,         # DB: cron_exp -> API: cron
            delay=s.random_delay,    # DB: random_delay -> API: delay
            last_run=s.last_run,
            last_status=s.last_status
        )
        for s in scripts
    ]

@app.post("/api/scripts", response_model=ScriptResponse)
def create_script(s: ScriptBase, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if db.query(Script).filter(Script.name == s.name).first():
        raise HTTPException(status_code=400, detail="Script name already exists")
    
    new_s = Script(
        name=s.name, 
        code=s.code, 
        requirements=s.requirements,
        cron_exp=s.cron,         # API: cron -> DB: cron_exp
        random_delay=s.delay     # API: delay -> DB: random_delay
    )
    db.add(new_s)
    db.commit()
    db.refresh(new_s)
    add_job_to_scheduler(new_s)
    
    # 手动构建响应
    return ScriptResponse(
        id=new_s.id,
        name=new_s.name,
        code=new_s.code,
        requirements=new_s.requirements,
        cron=new_s.cron_exp,
        delay=new_s.random_delay,
        last_run=new_s.last_run,
        last_status=new_s.last_status
    )

@app.put("/api/scripts/{script_id}", response_model=ScriptResponse)
def update_script(script_id: int, s: ScriptBase, db: Session = Depends(get_db), u=Depends(get_current_user)):
    item = db.query(Script).filter(Script.id == script_id).first()
    if not item: raise HTTPException(status_code=404, detail="Script not found")
    
    item.name = s.name
    item.code = s.code
    item.requirements = s.requirements
    item.cron_exp = s.cron
    item.random_delay = s.delay
    
    db.commit()
    db.refresh(item)
    add_job_to_scheduler(item)
    
    # 手动构建响应
    return ScriptResponse(
        id=item.id,
        name=item.name,
        code=item.code,
        requirements=item.requirements,
        cron=item.cron_exp,
        delay=item.random_delay,
        last_run=item.last_run,
        last_status=item.last_status
    )

@app.delete("/api/scripts/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    item = db.query(Script).filter(Script.id == script_id).first()
    if not item: raise HTTPException(status_code=404)
    
    try: scheduler.remove_job(str(script_id))
    except: pass
    
    venv_path = os.path.join(VENVS_DIR, str(script_id))
    if os.path.exists(venv_path):
        try: shutil.rmtree(venv_path, ignore_errors=True)
        except: pass

    db.delete(item)
    db.commit()
    return {"status": "deleted"}

@app.post("/api/scripts/{script_id}/run")
async def run_now(script_id: int, u=Depends(get_current_user)):
    asyncio.create_task(run_script_task(script_id, 0))
    return {"status": "triggered"}

@app.get("/api/secrets", response_model=List[SecretResponse])
def get_secrets(db: Session = Depends(get_db), u=Depends(get_current_user)):
    return db.query(Secret).all()

@app.post("/api/secrets")
def save_secret(s: SecretCreate, db: Session = Depends(get_db), u=Depends(get_current_user)):
    exist = db.query(Secret).filter(Secret.key == s.key).first()
    if exist:
        exist.value = s.value
        db.commit()
        return {"id": exist.id, "key": exist.key}
    
    new_s = Secret(key=s.key, value=s.value)
    db.add(new_s)
    db.commit()
    db.refresh(new_s)
    return {"id": new_s.id, "key": new_s.key}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(status_code=404)
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx): return FileResponse(idx)
    return {"message": "Frontend not found"}
