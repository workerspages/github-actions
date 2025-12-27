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

# ==========================================
# 1. 配置与初始化
# ==========================================

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/fluxtask.db")
# JWT 配置 (生产环境请在 Docker 环境变量中设置 JWT_SECRET)
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # Token 有效期 7 天

# 目录配置
SCRIPTS_DIR = "/app/scripts"
STATIC_DIR = "/app/static"
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# 数据库引擎 (SQLite 需要 check_same_thread=False)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 密码哈希与 JWT 工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 调度器实例
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
    code = Column(Text)              # Python 代码内容
    cron_exp = Column(String)        # Cron 表达式 "0 8 * * *"
    random_delay = Column(Integer, default=0) # 最大随机延时(秒)
    is_active = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)  # 上次运行时间
    last_status = Column(String, nullable=True) # Success / Failed / Error

class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)

# 创建表结构
Base.metadata.create_all(bind=engine)

# ==========================================
# 3. Pydantic 数据校验模型 (Schemas)
# ==========================================

class ScriptBase(BaseModel):
    name: str
    code: str
    cron: str
    delay: int = 0

class ScriptResponse(ScriptBase):
    id: int
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    
    class Config:
        # Pydantic V2 适配
        from_attributes = True

class SecretCreate(BaseModel):
    key: str
    value: str

class SecretResponse(BaseModel):
    id: int
    key: str
    # 不返回 value 以保护隐私
    
    class Config:
        # Pydantic V2 适配
        from_attributes = True

# ==========================================
# 4. 辅助函数 (Utils & Auth)
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
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# ==========================================
# 5. 核心逻辑：任务执行器
# ==========================================

async def run_script_task(script_id: int, override_delay: int = -1):
    """
    执行脚本的核心逻辑
    :param script_id: 脚本ID
    :param override_delay: 如果 >= 0，则忽略数据库设置的随机延时，直接使用此值（用于手动触发）
    """
    db = SessionLocal()
    try:
        script = db.query(Script).filter(Script.id == script_id).first()
        if not script:
            logger.warning(f"Task ID {script_id} not found in DB.")
            return

        # 1. 处理延时
        delay = 0
        if override_delay >= 0:
            delay = override_delay # 手动触发通常设为0
        elif script.random_delay > 0:
            delay = random.randint(0, script.random_delay)
        
        if delay > 0:
            logger.info(f"Task [{script.name}] sleeping for {delay} seconds (Anti-Bot)...")
            await asyncio.sleep(delay)

        # 2. 准备代码文件
        # 为了避免文件名冲突，使用简单的清理逻辑
        safe_name = "".join([c for c in script.name if c.isalnum() or c in (' ', '_', '-')]).strip()
        file_path = os.path.join(SCRIPTS_DIR, f"{safe_name}_{script.id}.py")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script.code)

        # 3. 注入 Secrets 到环境变量
        env_vars = os.environ.copy()
        secrets_list = db.query(Secret).all()
        for s in secrets_list:
            env_vars[s.key] = s.value
        
        # 4. 强制无缓冲输出
        env_vars["PYTHONUNBUFFERED"] = "1"

        logger.info(f"Executing script: {script.name}")
        
        # 5. 执行子进程 (subprocess)
        process = await asyncio.create_subprocess_exec(
            "python3", file_path,
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
            logger.info(f"Task [{script.name}] Success.\nOutput: {stdout_str}")
        else:
            script.last_status = "Failed"
            logger.error(f"Task [{script.name}] Failed.\nError: {stderr_str}\nOutput: {stdout_str}")
        
        db.commit()

    except Exception as e:
        logger.error(f"System Error running task {script_id}: {e}")
        try:
            if 'script' in locals() and script:
                script.last_status = "Error"
                db.commit()
        except:
            pass
    finally:
        db.close()

def add_job_to_scheduler(script: Script):
    """将脚本注册到 APScheduler"""
    # 先移除旧任务（如果存在）
    try:
        scheduler.remove_job(str(script.id))
    except:
        pass

    if not script.is_active:
        return

    try:
        # 解析 cron 表达式: "0 8 * * *" -> minute, hour, day, month, day_of_week
        parts = script.cron_exp.strip().split()
        if len(parts) != 5:
            logger.warning(f"Invalid Cron expression for {script.name}: {script.cron_exp}")
            return
        
        scheduler.add_job(
            run_script_task,
            CronTrigger(
                minute=parts[0], 
                hour=parts[1], 
                day=parts[2], 
                month=parts[3], 
                day_of_week=parts[4]
            ),
            id=str(script.id),
            args=[script.id],
            replace_existing=True
        )
        logger.info(f"Added job: {script.name} [{script.cron_exp}]")
    except Exception as e:
        logger.error(f"Failed to add job {script.name}: {e}")

# ==========================================
# 6. FastAPI 应用与 API 路由
# ==========================================

app = FastAPI(
    title="FluxTask", 
    description="私有化定时任务与反爬虫签到面板", 
    version="1.0.0"
)

# 挂载静态文件 (前端)
# 确保在 Dockerfile 中 COPY 了前端 dist 到 /app/static
app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

@app.on_event("startup")
def startup_event():
    # 1. 启动调度器
    scheduler.start()
    logger.info("Scheduler started.")
    
    # 2. 初始化数据库和任务
    db = SessionLocal()
    
    # --- 初始化管理员账户 (支持环境变量配置) ---
    default_user = os.getenv("ADMIN_USER", "admin")
    default_pass = os.getenv("ADMIN_PASSWORD", "admin")
    
    existing_user = db.query(User).filter(User.username == default_user).first()
    if not existing_user:
        hashed = pwd_context.hash(default_pass)
        db.add(User(username=default_user, hashed_password=hashed))
        db.commit()
        logger.info(f"Created default admin user: {default_user}")
    
    # 加载所有脚本到调度器
    scripts = db.query(Script).filter(Script.is_active == True).all()
    for s in scripts:
        add_job_to_scheduler(s)
    
    db.close()

# --- 登录接口 ---

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# --- 脚本管理接口 ---

@app.get("/api/scripts", response_model=List[ScriptResponse])
def get_scripts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Script).all()

@app.post("/api/scripts", response_model=ScriptResponse)
def create_script(
    script_in: ScriptBase, 
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # 检查重名
    if db.query(Script).filter(Script.name == script_in.name).first():
        raise HTTPException(status_code=400, detail="Script name already exists")
    
    new_script = Script(
        name=script_in.name,
        code=script_in.code,
        cron_exp=script_in.cron,
        random_delay=script_in.delay
    )
    db.add(new_script)
    db.commit()
    db.refresh(new_script)
    
    # 加入调度器
    add_job_to_scheduler(new_script)
    return new_script

@app.put("/api/scripts/{script_id}", response_model=ScriptResponse)
def update_script(
    script_id: int,
    script_in: ScriptBase,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    script.name = script_in.name
    script.code = script_in.code
    script.cron_exp = script_in.cron
    script.random_delay = script_in.delay
    
    db.commit()
    db.refresh(script)
    
    # 更新调度器
    add_job_to_scheduler(script)
    return script

@app.delete("/api/scripts/{script_id}")
def delete_script(script_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    # 从调度器移除
    try:
        scheduler.remove_job(str(script_id))
    except:
        pass
    
    db.delete(script)
    db.commit()
    return {"status": "deleted"}

@app.post("/api/scripts/{script_id}/run")
async def run_script_now(script_id: int, user: User = Depends(get_current_user)):
    """
    手动立即触发，忽略随机延时 (delay=0)
    """
    # 使用 asyncio.create_task 不阻塞 API 返回
    asyncio.create_task(run_script_task(script_id, override_delay=0))
    return {"status": "triggered"}

# --- Secrets 管理接口 ---

@app.get("/api/secrets", response_model=List[SecretResponse])
def get_secrets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Secret).all()

@app.post("/api/secrets")
def create_or_update_secret(
    secret_in: SecretCreate, 
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    existing = db.query(Secret).filter(Secret.key == secret_in.key).first()
    if existing:
        existing.value = secret_in.value
        db.commit()
        return {"status": "updated", "id": existing.id}
    else:
        new_secret = Secret(key=secret_in.key, value=secret_in.value)
        db.add(new_secret)
        db.commit()
        db.refresh(new_secret)
        return {"status": "created", "id": new_secret.id}

# --- 前端路由处理 (SPA Fallback) ---
# 必须放在最后，用于处理 Vue 路由的刷新问题
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    # 如果请求的是 API，但没匹配到，返回 404
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # 否则返回前端入口 index.html
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not initialized. Please build Docker image."}
