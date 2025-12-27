import os
import random
import asyncio
import subprocess
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from passlib.context import CryptContext
from jose import JWTError, jwt
from loguru import logger

# --- 配置 ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"

# --- 数据库初始化 ---
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 模型 ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    code = Column(Text)
    cron_exp = Column(String) # e.g., "0 9 * * *"
    random_delay = Column(Integer, default=0) # 最大随机延时(秒)
    is_active = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)
    last_status = Column(String, nullable=True) # "Success", "Failed"

class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True)
    value = Column(String)

Base.metadata.create_all(bind=engine)

# --- 工具与认证 ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
scheduler = AsyncIOScheduler()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 核心：执行脚本 (带随机延时) ---
async def run_script_task(script_id: int):
    db = SessionLocal()
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script or not script.is_active:
        db.close()
        return

    # 1. 随机延时逻辑 (防封号关键)
    if script.random_delay > 0:
        delay = random.randint(0, script.random_delay)
        logger.info(f"Task [{script.name}] sleeping for {delay} seconds...")
        await asyncio.sleep(delay)

    # 2. 注入 Secrets
    env_vars = os.environ.copy()
    secrets_list = db.query(Secret).all()
    for s in secrets_list:
        env_vars[s.key] = s.value
    
    # 3. 写入临时文件
    file_path = f"/app/scripts/{script.name}.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(script.code)
    
    # 4. 执行
    logger.info(f"Executing [{script.name}]...")
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", file_path,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        script.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        script.last_status = "Success" if proc.returncode == 0 else "Failed"
        # 这里你可以拓展把日志存入数据库
        logger.info(f"Result [{script.name}]: {stdout.decode()}")
        if stderr: logger.error(f"Error [{script.name}]: {stderr.decode()}")
        
    except Exception as e:
        script.last_status = "Error"
        logger.error(f"Execution failed: {e}")
    
    db.commit()
    db.close()

# --- API ---
app = FastAPI(title="FluxTask")

# 挂载前端 (生产环境)
app.mount("/assets", StaticFiles(directory="/app/static/assets"), name="assets")

@app.on_event("startup")
def start_scheduler():
    scheduler.start()
    # 重新加载数据库中的任务
    db = SessionLocal()
    scripts = db.query(Script).filter(Script.is_active == True).all()
    for s in scripts:
        add_job_to_scheduler(s)
    
    # 初始化默认用户 admin / admin
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(username="admin", hashed_password=pwd_context.hash("admin"))
        db.add(admin)
        db.commit()
    db.close()

def add_job_to_scheduler(script: Script):
    # 解析 Cron (简单的 5 段式)
    try:
        parts = script.cron_exp.split()
        if len(parts) != 5: return
        scheduler.add_job(
            run_script_task,
            CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]),
            args=[script.id],
            id=str(script.id),
            replace_existing=True
        )
    except Exception as e:
        logger.error(f"Cron Error: {e}")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = jwt.encode({"sub": user.username}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")

# 脚本 CRUD
@app.get("/api/scripts")
def list_scripts(user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Script).all()

@app.post("/api/scripts")
def create_script(
    name: str = Body(...), 
    code: str = Body(...), 
    cron: str = Body(...), 
    delay: int = Body(0),
    user: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    script = Script(name=name, code=code, cron_exp=cron, random_delay=delay)
    db.add(script)
    db.commit()
    db.refresh(script)
    if script.is_active:
        add_job_to_scheduler(script)
    return script

# Secret CRUD
@app.get("/api/secrets")
def list_secrets(user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # 隐藏值
    secrets = db.query(Secret).all()
    return [{"id": s.id, "key": s.key, "value": "******"} for s in secrets]

@app.post("/api/secrets")
def create_secret(key: str = Body(...), value: str = Body(...), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # 如果存在则更新
    existing = db.query(Secret).filter(Secret.key == key).first()
    if existing:
        existing.value = value
    else:
        s = Secret(key=key, value=value)
        db.add(s)
    db.commit()
    return {"status": "ok"}

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    return FileResponse("/app/static/index.html")
