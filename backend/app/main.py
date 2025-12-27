# --- 现有代码 ... ---

# 1. 修改/更新脚本 (PUT)
@app.put("/api/scripts/{script_id}")
def update_script(
    script_id: int,
    name: str = Body(...),
    code: str = Body(...),
    cron: str = Body(...),
    delay: int = Body(...),
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    script.name = name
    script.code = code
    script.cron_exp = cron
    script.random_delay = delay
    
    # 更新调度器中的任务
    try:
        add_job_to_scheduler(script)
    except Exception as e:
        logger.error(f"Scheduler update failed: {e}")

    db.commit()
    return {"status": "updated"}

# 2. 删除脚本 (DELETE)
@app.delete("/api/scripts/{script_id}")
def delete_script(script_id: int, user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    # 从调度器移除
    try:
        scheduler.remove_job(str(script_id))
    except:
        pass # Job可能本来就不存在

    db.delete(script)
    db.commit()
    return {"status": "deleted"}

# 3. 手动立即运行 (POST) - 用于测试脚本
@app.post("/api/scripts/{script_id}/run")
async def run_script_now(script_id: int, user: str = Depends(get_current_user)):
    # 异步触发，不等待结果直接返回
    asyncio.create_task(run_script_task(script_id))
    return {"status": "triggered"}

# --- 现有代码结束 ---
