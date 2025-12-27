import os
import sys
import asyncio
import re
import requests  # type: ignore
import traceback
from telethon import TelegramClient
from telethon.sessions import StringSession
from typing import Dict, Any

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_SESSION_STR = os.getenv('TG_SESSION_STR')
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
TARGET_BOT_USERNAME = '@ICMP9_Bot'
CHECK_WAIT_TIME = 5
# ============================================

COLORS = {'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m', 'cyan': '\033[96m', 'reset': '\033[0m'}
SYMBOLS = {'check': '✅', 'warning': '⚠️', 'arrow': '➡️', 'error': '❌'}


def log(color_key: str, symbol_key: str, message: str):
    color = COLORS.get(color_key, COLORS['reset'])
    icon = SYMBOLS.get(symbol_key, symbol_key)
    print(f"{color}{icon} {message}{COLORS['reset']}")


def send_tg_notification(data: Dict[str, str]):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置TG通知变量，跳过通知")
        return

    text = (
        f"🤖 *ICMP9 签到报告* 🤖\n"
        f"━━━━━━━━━━━━\n"
        f"👤 账户: {data.get('user', '未知')}\n"
        f"📅 状态: {data.get('status', '未知')}\n"
        f"🎁 今日已获: {data.get('gained', '0 GB')}\n"
        f"🔥 连续签到: {data.get('streak', '未知')}\n"
        f"━━━━━━━━━━━━\n"
        f"📦 总配额: {data.get('total', '未知')}\n"
        f"📈 已使用: {data.get('used', '未知')}\n"
        f"📉 剩余量: {data.get('remaining', '未知')}\n"
        f"🖥️ 虚机数: {data.get('vm_count', '未知')}\n"
        f"📝 虚机列表: {data.get('vm_info', '无')}"
    )

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}, timeout=15).raise_for_status()
        log('green', 'check', "TG 通知已发送")
    except Exception as e:
        log('red', 'error', f"TG 通知发送失败: {e}")


def parse_all_info(text: str, current_data: Dict[str, str], parse_user: bool = False, parse_gained: bool = False) -> Dict[str, str]:
    if parse_user:
        user_match = re.search(r'📊\s*([^\n\r]+)', text)
        if user_match:
            name = user_match.group(1).split('━━')[0].strip().replace('*', '')
            current_data['user'] = name
            log('green', 'check', f"解析到用户名: {name}")

    if parse_gained:
        gained = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB|KB|B)', text, re.I)
        if gained:
            current_data['gained'] = f"{gained.group(1)} {gained.group(2).upper()}"

    streak = re.search(r'连续签到[：:\s]+(\d+)', text)
    if streak:
        current_data['streak'] = f"{streak.group(1)} 天"

    quota = re.search(r'配额[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if quota:
        current_data['total'] = quota.group(1)

    used = re.search(r'已用[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if used:
        current_data['used'] = used.group(1)

    rem = re.search(r'剩余[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if rem:
        current_data['remaining'] = rem.group(1)

    vms = re.search(r'虚机[：:\s]+(\d+)', text)
    if vms:
        current_data['vm_count'] = f"{vms.group(1)} 台"

    return current_data


async def safe_click(msg, button_text):
    if not msg or not msg.buttons:
        log('red', 'error', "消息中没有按钮可点击")
        return False

    coords = {'账户': (0, 1), '虚机': (0, 2)}
    if button_text in coords:
        row, col = coords[button_text]
        try:
            await msg.click(row, col)
            log('green', 'check', f"已执行坐标点击: [{button_text}]")
            return True
        except Exception as e:
            log('red', 'error', f"点击 [{button_text}] 失败: {e}")
    return False


async def main():
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "环境变量缺失")
        return

    if TG_SESSION_STR:
        client = TelegramClient(StringSession(TG_SESSION_STR), int(TG_API_ID), TG_API_HASH)
    else:
        log('red', 'error', "未检测到 TG_SESSION_STR 环境变量或变量为空")
        log('yellow', 'warning', "请先运行转换脚本获取 Session 字符串，并配置到环境变量中")
        sys.exit(1)

    info = {
        'user': '未知',
        'status': '失败',
        'gained': '未知',
        'streak': '未知',
        'total': '未知',
        'used': '未知',
        'remaining': '未知',
        'vm_count': '未知',
        'vm_info': '未知'
    }

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "tg_session 已失效, 请更新环境变量 TG_SESSION_STR")
            return

        log('green', 'check', f"TG 登录成功, 连接机器人: {TARGET_BOT_USERNAME}")
        bot = await client.get_entity(TARGET_BOT_USERNAME)

        # 1. 签到
        log('cyan', 'arrow', "发送签到指令 /checkin")
        await client.send_message(bot, '/checkin')
        log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒获取签到回复")
        await asyncio.sleep(CHECK_WAIT_TIME)

        msgs = await client.get_messages(bot, limit=1)
        if not msgs:
            log('red', 'error', "未收到回复")
            return
        msg_obj = msgs[0]

        info = parse_all_info(msg_obj.text, info, parse_user=False, parse_gained=True)
        info['status'] = "✅ 签到成功" if "成功" in msg_obj.text else "ℹ️ 今日已签"

        # 2. 账户详情
        log('cyan', 'arrow', "请求账户详情...")
        if await safe_click(msg_obj, '账户'):
            log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒更新账户消息")
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            if refreshed:
                info = parse_all_info(refreshed.text, info, parse_user=True, parse_gained=False)
                msg_obj = refreshed
            else:
                log('yellow', 'warning', "账户信息获取失败")

        # 3. 虚机详情
        log('cyan', 'arrow', "请求虚拟机列表...")
        if await safe_click(msg_obj, '虚机'):
            log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒更新虚拟机信息")
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            if refreshed:
                clean_text = refreshed.text.replace('*', '')
                if "虚拟机列表" in clean_text:
                    clean_text = clean_text.split("虚拟机列表")[-1]
                clean_text = clean_text.strip()
                info['vm_info'] = clean_text if clean_text else "您当前没有虚拟机"
                log('green', 'check', f"虚拟机列表: {info['vm_info']}")
            else:
                log('yellow', 'warning', "虚拟机列表获取失败")

    except Exception as e:
        traceback.print_exc()
        err_msg = f"严重错误: {type(e).__name__} - {str(e)}"
        log('red', 'error', err_msg)
        info['status'] = "错误"
    finally:
        if client.is_connected():
            await client.disconnect()
            log('cyan', 'arrow', "连接已断开")
        # === 最终通知 ===
        send_tg_notification(info)
        log('green', 'check', "任务执行完毕，结果统计：")
        log('cyan', 'arrow', f"最终状态: {info['status']}")
        log('cyan', 'arrow', f"连续签到: {info['streak']}")
        log('cyan', 'arrow', f"今日获得: {info['gained']}")
        log('cyan', 'arrow', f"当前总配额: {info['total']}")
        log('cyan', 'arrow', f"已用配额: {info['used']}")
        log('cyan', 'arrow', f"剩余配额: {info['remaining']}")
        log('cyan', 'arrow', f"虚拟机数量: {info['vm_count']}")
        log('cyan', 'arrow', f"虚拟机详情: {info['vm_info']}")

        if not any(k in info['status'] for k in ["成功", "已签"]):
            sys.exit(1)

if __name__ == '__main__':
    log('cyan', 'arrow', "=== 执行 ICMP9 签到任务 ===")
    asyncio.run(main())
