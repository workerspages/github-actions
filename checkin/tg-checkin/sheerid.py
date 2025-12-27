import os
import re
import sys
import asyncio
import requests  # type: ignore
import traceback
from telethon import TelegramClient
from telethon.tl.custom.message import Message
from telethon.sessions import StringSession
from typing import Dict, Any, Tuple

# Windows事件循环策略，兼容win系统运行
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_SESSION_STR = os.getenv('TG_SESSION_STR')  # 你的 TG Session 字符串
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')      # 你的通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')          # 你的个人 Chat ID (接收通知用)
TARGET_BOT_USERNAME = '@auto_sheerid_bot'     # 签到目标机器人用户名
CHECK_WAIT_TIME = 5                           # 等待机器人回复的时间（秒）
DEFAULT_GAINED_POINTS = "未知"                 # 获得积分的默认值
DEFAULT_TOTAL_POINTS = "未知"                  # 总积分的默认值
# ============================================

# 定义颜色和符号 (用于日志美化)
COLORS: Dict[str, str] = {
    'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
    'cyan': '\033[96m', 'reset': '\033[0m'
}
SYMBOLS: Dict[str, str] = {'check': '✓', 'warning': '⚠', 'arrow': '➜', 'error': '✗'}


# 日志函数
def log(color: str, symbol: str, message: str):
    print(f"{COLORS[color]}{SYMBOLS[symbol]} {message}{COLORS['reset']}")


# 发送 Telegram 消息通知模板
def send_tg_notification(status: str, gained: str, total: str):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return

    target_bot_link = TARGET_BOT_USERNAME.replace('@', 't.me/') if TARGET_BOT_USERNAME.startswith('@') else TARGET_BOT_USERNAME  # 构造链接
    status_emoji = "✅" if status == "成功" else ("⭐" if status == "今日已签到" else "❌")
    notification_text = (
        f"🤖 *Auto SheerID 签到通知* 🤖\n"
        f"====================\n"
        f"{status_emoji} 状态: {status}\n"
        f"🎯 目标: [{TARGET_BOT_USERNAME}]({target_bot_link})\n"
        f"📌 今日获得: {gained}\n"
        f"📊 当前总分: {total}"
    )

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload: Dict[str, Any] = {
        'chat_id': TG_CHAT_ID,
        'text': notification_text,
        'parse_mode': 'Markdown'
    }

    try:
        requests.post(url, data=payload, timeout=10).raise_for_status()
    except requests.exceptions.RequestException as e:
        log('red', 'error', f"Telegram 通知发送失败: {e}")


# 解析积分信息
def parse_points(message_text: str) -> Tuple[str, str]:
    """
    从消息文本中解析 '获得积分' 和 '当前积分'。如果未找到，返回默认值
    """
    gained_points = DEFAULT_GAINED_POINTS
    total_points = DEFAULT_TOTAL_POINTS
    gained_match = re.search(r'获得积分\D*(\d+)', message_text)
    total_match = re.search(r'当前积分\D*(\d+)', message_text)

    if gained_match:
        gained_points = f"{gained_match.group(1)}分"
    if total_match:
        total_points = f"{total_match.group(1)}分"

    return gained_points, total_points


# 等待并获取目标机器人最新回复
async def get_bot_reply(client: TelegramClient, bot_entity: Any, check_limit: int = 5) -> Message | None:
    log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒后读取机器人回复")
    await asyncio.sleep(CHECK_WAIT_TIME)

    target_id = bot_entity.id # 获取签到机器人的ID
    async for msg in client.iter_messages(bot_entity, limit=check_limit):
        if isinstance(msg, Message) and msg.sender_id == target_id and not msg.out:
            return msg
    return None


# 执行签到主逻辑
async def check_in():
    # 检查核心登录变量
    required_vars = {'TG_API_ID': TG_API_ID, 'TG_API_HASH': TG_API_HASH}
    missing_vars = [name for name, val in required_vars.items() if not val]
    if missing_vars:
        err_msg = f"TG 登录失败：缺少必要的变量: {', '.join(missing_vars)}！请检查 GitHub Secrets 设置"
        log('red', 'error', err_msg)
        sys.exit(1)

    if TG_SESSION_STR:
        client = TelegramClient(StringSession(TG_SESSION_STR), int(TG_API_ID), TG_API_HASH)
    else:
        log('red', 'error', "未检测到 TG_SESSION_STR 环境变量或变量为空")
        log('yellow', 'warning', "请先运行转换脚本获取 Session 字符串，并配置到环境变量中")
        sys.exit(1)

    log('cyan', 'arrow', "启动 TG 客户端")
    status = "失败"
    gained_points = DEFAULT_GAINED_POINTS
    total_points = DEFAULT_TOTAL_POINTS

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "tg_session 已失效, 请更新环境变量 TG_SESSION_STR")
            return

        try:
            bot_entity = await client.get_entity(TARGET_BOT_USERNAME)
            log('cyan', 'arrow', f"已连接到机器人: {TARGET_BOT_USERNAME}")
        except Exception as e:
            log('red', 'error', f"无法找到机器人 {TARGET_BOT_USERNAME}: {e}")
            return

        log('cyan', 'arrow', "发送 /qd 签到命令")
        await client.send_message(bot_entity, '/qd')
        
        reply = await get_bot_reply(client, bot_entity)
        if reply and reply.text:
            reply_text = reply.text
            log('green', 'check', f"收到回复:\n{reply_text}")

            # 情况 A: 签到成功
            if '签到成功' in reply_text:
                status = "成功"
                log('green', 'check', "判断为：签到成功")
                gained_points, total_points = parse_points(reply_text)

            # 情况 B: 今日已签到
            elif '已经签到' in reply_text or '已签到' in reply_text:
                status = "今日已签到"
                log('yellow', 'warning', "判断为：今日已签到，尝试查询余额")
                await client.send_message(bot_entity, '/balance')
                balance_reply = await get_bot_reply(client, bot_entity)
                if balance_reply and balance_reply.text:
                    log('green', 'check', f"收到余额回复:\n{balance_reply.text}")
                    _, total_points = parse_points(balance_reply.text)
                else:
                    log('red', 'error', "查询余额未收到回复")

            else:
                status = "未知响应"
                log('red', 'error', "无法识别机器人的回复内容")
        else:
            log('red', 'error', "未收到机器人回复")

    except Exception as e:
        traceback.print_exc()
        err_msg = f"严重错误: {type(e).__name__} - {str(e)}"
        log('red', 'error', err_msg)
        status = "错误"
    finally:
        if client.is_connected():
            await client.disconnect()
            log('cyan', 'arrow', "连接已安全断开")
        # === 最终通知 ===
        send_tg_notification(status, gained_points, total_points)
        log('green', 'check', "任务执行完毕! 结果统计：")
        log('cyan', 'arrow', f"最终状态: {status}")
        log('cyan', 'arrow', f"今日获得: {gained_points}")
        log('cyan', 'arrow', f"当前总分: {total_points}")

        if not any(k in status for k in ["成功", "今日已签到"]):
            sys.exit(1)

if __name__ == '__main__':
    log('cyan', 'arrow', "=== 执行 SheerID 签到任务 ===")
    asyncio.run(check_in())
