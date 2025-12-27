import os
import time
import requests
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# -------------------------------
log_buffer = []

def log(msg):
    print(msg)
    log_buffer.append(msg)
# -------------------------------

# Telegram 推送函数
def send_tg_log():
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ Telegram 未配置，跳过推送")
        return

    utc_now = datetime.utcnow()
    beijing_now = utc_now + timedelta(hours=8)
    now_str = beijing_now.strftime("%Y-%m-%d %H:%M:%S") + " UTC+8"

    final_msg = f"📌 Netlib 保活执行日志\n🕒 {now_str}\n\n" + "\n".join(log_buffer)

    for i in range(0, len(final_msg), 3900):
        chunk = final_msg[i:i+3900]
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/sendMessage",
                params={"chat_id": chat_id, "text": chunk},
                timeout=10
            )
            if resp.status_code == 200:
                print(f"✅ Telegram 推送成功 [{i//3900 + 1}]")
            else:
                print(f"⚠️ Telegram 推送失败 [{i//3900 + 1}]: HTTP {resp.status_code}, 响应: {resp.text}")
        except Exception as e:
            print(f"⚠️ Telegram 推送异常 [{i//3900 + 1}]: {e}")

# 从环境变量解析多个账号, 格式为多行，每行: username:password
accounts_env = os.environ.get("NETLIB_ACCOUNTS", "")
accounts = []

# 使用换行符分割，处理可能的 \r\n 或 \n
for item in accounts_env.strip().split('\n'):
    item = item.strip()
    if item:
        try:
            # 使用冒号:分割用户名和密码
            username, password = item.split(":", 1)
            accounts.append({"username": username.strip(), "password": password.strip()})
        except ValueError:
            log(f"⚠️ 忽略格式错误的账号项: {item} (预期格式: username:password)")

fail_msgs = [
    "Invalid credentials.",
    "Not connected to server.",
    "Error with the login: login size should be between 2 and 50 (currently: 1)"
]

def login_account(playwright, USER, PWD):
    log(f"🚀 开始登录账号: {USER}")
    try:
        # 使用 headless=True (无头模式)
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.netlib.re/")
        time.sleep(5)

        page.get_by_text("Login").click()
        time.sleep(2)
        page.get_by_role("textbox", name="Username").fill(USER)
        time.sleep(2)
        page.get_by_role("textbox", name="Password").fill(PWD)
        time.sleep(2)
        page.get_by_role("button", name="Validate").click()
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 检查是否登录成功
        success_text = "You are the exclusive owner of the following domains."
        if page.query_selector(f"text={success_text}"):
            log(f"✅ 账号 {USER} 登录成功")
            time.sleep(5)
        else:
            # 检查是否有预设的失败消息
            failed_msg = None
            for msg in fail_msgs:
                # 使用 page.inner_text() 或其他方式检查页面内容
                if page.locator("body").inner_text().find(msg) != -1:
                    failed_msg = msg
                    break
            
            if failed_msg:
                log(f"❌ 账号 {USER} 登录失败: {failed_msg}")
            else:
                log(f"❌ 账号 {USER} 登录失败: 未知错误 (当前URL: {page.url})")

        context.close()
        browser.close()

    except Exception as e:
        log(f"❌ 账号 {USER} 登录异常: {e}")

def run():
    if not accounts:
        log("⚠️ 未找到任何账号配置，请检查 NETLIB_ACCOUNTS 环境变量。")
        return

    with sync_playwright() as playwright:
        for acc in accounts:
            login_account(playwright, acc["username"], acc["password"])
            time.sleep(2)

if __name__ == "__main__":
    run()
    send_tg_log()  # 发送日志
