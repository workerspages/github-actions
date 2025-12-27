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
TG_SESSION_STR = os.getenv('TG_SESSION_STR')
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')      # 你的通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')          # 你的个人或群组 Chat ID
TG_CHANNEL = '@cloudcatgroup'                 # 签到目标频道名, 格式: @username
TARGET_BOT_USERNAME = '@CloudCatOfficialBot'  # 签到机器人用户名, 格式: @username
CHECK_WAIT_TIME = 10                          # 等待机器人回复的时间（秒）
DEFAULT_GAINED_POINTS = "未知"                # 获得积分的默认值
DEFAULT_TOTAL_POINTS = "未知"                 # 当前总分的默认值
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

    channel_link = TG_CHANNEL.replace('@', 't.me/') if TG_CHANNEL.startswith('@') else TG_CHANNEL  # 构造频道链接
    status_emoji = "✅" if status == "成功" else ("ℹ️" if status == "今日已签到" else "❌")  # 状态 Emoji
    notification_text = (
        f"🎉 *Cloud Cat 签到通知* 🎉\n"
        f"====================\n"
        f"{status_emoji} 状态: {status}\n"
        f"📢 频道: [{TG_CHANNEL}]({channel_link})\n"
        f"📌 今日签到积分: {gained}\n"
        f"📊 您的总积分: {total}"
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


# 解析今日签到积分和总积分
def parse_points_from_message(message_text: str, is_points_command_reply: bool) -> Tuple[str, str]:
    gained_points = DEFAULT_GAINED_POINTS
    total_points = DEFAULT_TOTAL_POINTS

    # 今日已签到的情况
    if is_points_command_reply:
        gained_match = re.search(r'CheckInAddPoint[:：]\s*(\d+\.?\d*)\s*⭐?', message_text, re.IGNORECASE)
        total_match = re.search(r'(?:当前积分[:：]|current points[:：]\s*)(\d+\.?\d*)', message_text, re.IGNORECASE)
    # 今日未签到的情况
    else:
        gained_match = re.search(r'(?:获得|you got)\s*(\d+\.?\d*)\s?⭐', message_text, re.IGNORECASE)
        total_match = re.search(r'(?:当前积分[:：]|current points:\s*)(\d+\.?\d*)\s?⭐', message_text, re.IGNORECASE)

    if gained_match:
        gained_points = f"{gained_match.group(1)} ⭐"
    if total_match:
        try:
            total_points = f"{int(float(total_match.group(1)))} ⭐"
        except ValueError:
            pass

    return gained_points, total_points


# 等待并获取目标机器人最新回复
async def get_bot_reply(client: TelegramClient, channel_entity: Any, check_limit: int, target_bot_id: int, min_id: int = 0) -> Message | None:
    log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒后查找机器人回复...")
    await asyncio.sleep(CHECK_WAIT_TIME)
    
    log('cyan', 'arrow', f"开始查找最近 {check_limit} 条消息...")
    message_count = 0

    async for msg in client.iter_messages(channel_entity, limit=check_limit):
        if isinstance(msg, Message) and msg.sender_id == target_bot_id:
            if msg.id > min_id:
                log('green', 'check', f"找到来自 {TARGET_BOT_USERNAME} 的回复")
                return msg
    return None


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

    log('cyan', 'arrow', "启动 TG 并尝试登录")
    status = "失败"
    gained_points = DEFAULT_GAINED_POINTS
    total_points = DEFAULT_TOTAL_POINTS
    check_limit = 30  # 消息查找范围

    # 签到逻辑：先发送 /checkin，成功则直接获取积分；若为“已签到”则发送 /points 获取积分
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "tg_session 已失效, 请更新环境变量 TG_SESSION_STR")
            return

        # 获取频道对象
        channel_entity = await client.get_entity(TG_CHANNEL)
        log('cyan', 'arrow', f"已成功连接频道：{channel_entity.title}")

        # 动态获取机器人 ID
        target_bot_entity = await client.get_entity(TARGET_BOT_USERNAME)
        current_bot_id = target_bot_entity.id
        log('green', 'check', f"已成功获取签到机器人ID: {current_bot_id}")
        
        # 发送签到指令 /checkin
        log('cyan', 'arrow', "发送 /checkin 签到")
        sent_msg = await client.send_message(channel_entity, '/checkin')

        # 获取机器人回复
        reply = await get_bot_reply(client, channel_entity, check_limit, current_bot_id, min_id=sent_msg.id)
        if reply and reply.text:
            log('green', 'check', f"收到 /checkin 回复，内容:\n{reply.text}")

            # 检查是否签到成功
            if any(keyword in reply.text for keyword in ['成功', 'successful']):
                status = "成功"
                log('green', 'check', "签到成功")
                gained_points, total_points = parse_points_from_message(reply.text, False)

            # 检查是否已签到
            elif any(keyword in reply.text for keyword in ['已经签到过了', '今天已经签到', '今日已签到']):
                status = "今日已签到"
                log('yellow', 'warning', "今日已签到，发送 /points 获取积分详情")
                sent_points_msg = await client.send_message(channel_entity, '/points')
                
                points_reply = await get_bot_reply(client, channel_entity, check_limit, current_bot_id, min_id=sent_points_msg.id)
                if points_reply and points_reply.text:
                    log('green', 'check', f"收到 /points 回复，内容:\n{points_reply.text}")
                    gained_points, total_points = parse_points_from_message(points_reply.text, True)
                else:
                    log('red', 'error', "发送 /points 后未收到机器人回复")
            else:
                status = "失败"
                log('red', 'error', "未找到预期的签到成功或已签到关键词")
        else:
            status = "失败"
            log('red', 'error', "发送 /checkin 后未收到机器人回复")

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

        if any(k in status for k in ["失败", "错误"]):
            sys.exit(1)

if __name__ == '__main__':
    log('cyan', 'arrow', "=== 执行 CloudCat 签到任务 ===")
    asyncio.run(check_in())
