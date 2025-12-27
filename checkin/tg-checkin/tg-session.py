# 此脚本用于获取 tg_session 的字符串，作为签到脚本环境变量 TG_SESSION_STR 的值
# 需要安装以下依赖：pip install telethon pysocks
# 建议在本地运行，以避免泄露敏感数据

import asyncio
import socks  # type: ignore
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

# 配置信息
API_ID = 123123
API_HASH = '253368995333456338962'
PROXY = (socks.SOCKS5, '127.0.0.1', 10808)
SESSION_NAME = 'tg_session'


async def main():
    session_file = f"{SESSION_NAME}.session"
    exists = os.path.exists(session_file)

    if exists:
        print(f"检测到本地已存在 {session_file}，正在尝试转换...")
    else:
        print(f"未检测到本地 Session，请按照提示进行登录生成...")

    # 如果文件不存在，client.start() 会引导你输入手机号和验证码
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH, proxy=PROXY)

    try:
        await client.start()
        if await client.is_user_authorized():
            session_str = StringSession.save(client.session)
            print("\n" + "=" * 30)
            print("登录成功！你的 TG_SESSION_STR 如下：")
            print(session_str)
            print("=" * 30)
            print("\n你可以将上方字符串保存到环境变量或配置文件中。")
        else:
            print("错误：授权失败")

    except Exception as e:
        print(f"运行过程中出现错误: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
