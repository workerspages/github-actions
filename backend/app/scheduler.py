import time
import random
import subprocess
import os
import asyncio
from loguru import logger
from sqlalchemy.orm import Session

# 模拟 GitHub Actions 的环境变量注入
def get_env_vars(db: Session):
    # 从数据库获取 Name/Secret
    secrets = db.query(SecretModel).all()
    env = os.environ.copy()
    for secret in secrets:
        env[secret.key] = secret.value
    return env

async def execute_script_task(script_path: str, db_session, max_random_delay: int = 300):
    """
    执行脚本的任务函数
    :param max_random_delay: 最大随机延时(秒)，默认5分钟
    """
    # 1. 随机延时 (反爬虫关键)
    if max_random_delay > 0:
        delay = random.randint(0, max_random_delay)
        logger.info(f"任务 {script_path} 将延时 {delay} 秒后执行...")
        await asyncio.sleep(delay)

    # 2. 准备环境变量
    env_vars = get_env_vars(db_session)
    
    # 3. 执行脚本 (使用 subprocess 隔离)
    logger.info(f"开始执行: {script_path}")
    try:
        # 这里模拟 python 脚本执行，也可以支持 shell
        process = await asyncio.create_subprocess_exec(
            "python3", script_path,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        # 4. 保存日志 (类似 Github Actions 的 Console)
        save_log(script_path, stdout.decode(), stderr.decode())
        
    except Exception as e:
        logger.error(f"执行失败: {e}")

# 在 FastAPI 启动时初始化 APScheduler
# 添加任务时，不是直接添加 execute_script_task，而是通过 scheduler.add_job 添加
