import requests
import os
import sys
import re
from datetime import datetime, timedelta

# -----------------------------------------------------------------------
BASE_URL = "https://client.webhostmost.com"
LOGIN_URL = f"{BASE_URL}/login"
REDIRECT_URL = f"{BASE_URL}/clientarea.php"
EMAIL_FIELD = "username"
PASSWORD_FIELD = "password"
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
# -----------------------------------------------------------------------


def parse_users(users_secret):
    """解析 GitHub Secret 格式：邮箱:密码\\n邮箱2:密码2"""
    users = []
    if not users_secret:
        print("❌ 未找到 WHM_ACCOUNT 环境变量中的用户数据。")
        return users

    for line in users_secret.strip().split('\n'):
        parts = line.strip().split(':', 1)
        if len(parts) == 2:
            email, password = parts[0].strip(), parts[1].strip()
            users.append({'email': email, 'password': password})
        else:
            print(f"⚠️ 跳过格式错误的行: {line}")
    return users

def get_csrf_token(session):
    """从登录页提取 CSRF Token"""
    try:
        r = session.get(LOGIN_URL, timeout=15)
        r.raise_for_status()
        match = re.search(r'name="token"\s+value="([^"]+)"', r.text)
        if match:
            token = match.group(1)
            print(f"🔑 获取到 CSRF Token: {token[:8]}...")
            return token
        else:
            print("⚠️ 未找到 CSRF Token，可能页面结构已变。")
            return None
    except requests.RequestException as e:
        print(f"❌ 获取登录页时出错: {e}")
        return None

def extract_remaining_days():
    """
    精确计算剩余天数（向下取整）
    """
    TOTAL_DAYS = 45
    now = datetime.now()
    end_time = now + timedelta(days=TOTAL_DAYS)  # JS 逻辑: 登录时 + 45天
    remaining_timedelta = end_time - now
    remaining_days = remaining_timedelta.days
    return remaining_days

def attempt_login(email, password):
    """尝试登录并返回结果与剩余时间"""
    session = requests.Session()
    print(f"\n👤 尝试登录用户：{email}")

    token = get_csrf_token(session)
    if not token:
        print("⚠️ 获取 CSRF Token 失败，跳过此账号。")
        return {"email": email, "success": False, "reason": "无法获取 CSRF Token"}

    payload = {
        EMAIL_FIELD: email,
        PASSWORD_FIELD: password,
        "token": token,
        "rememberme": "on",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": LOGIN_URL,
        "Origin": BASE_URL,
    }

    try:
        response = session.post(LOGIN_URL, data=payload, headers=headers, allow_redirects=True, timeout=15)

        if REDIRECT_URL in response.url or "clientarea.php" in response.text.lower():
            print(f"✅ 成功登录用户 {email}，正在解析剩余时间...")
            remaining_days = extract_remaining_days()
            if remaining_days is not None:
                print(f"📆 剩余时间: {remaining_days} 天")
            else:
                print("⚠️ 无法获取剩余时间。")
            return {"email": email, "success": True, "days": remaining_days}

        elif "incorrect" in response.text.lower():
            print(f"❌ 登录失败：账号或密码错误。用户 {email}")
            return {"email": email, "success": False, "reason": "账号或密码错误"}

        elif "Invalid CSRF token" in response.text:
            print(f"❌ 登录失败：Token 无效。用户 {email}")
            return {"email": email, "success": False, "reason": "CSRF Token 无效"}

        else:
            print(f"⚠️ 登录失败：未知原因。URL: {response.url}")
            return {"email": email, "success": False, "reason": "未知错误"}

    except requests.exceptions.RequestException as e:
        print(f"❌ 登录用户 {email} 时发生错误: {e}")
        return {"email": email, "success": False, "reason": str(e)}


def send_tg_message(message):
    """通过 Telegram 发送通知"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ 未设置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 通知。")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            print("📨 Telegram 通知已发送。")
        else:
            print(f"⚠️ Telegram 通知发送失败: {r.status_code} {r.text}")
    except Exception as e:
        print(f"⚠️ Telegram 通知错误: {e}")


def main():
    user_credentials_secret = os.getenv('WHM_ACCOUNT')

    if not user_credentials_secret:
        print("错误：未设置 WHM_ACCOUNT 环境变量。请在 GitHub Secrets 中配置。")
        sys.exit(1)

    users = parse_users(user_credentials_secret)
    if not users:
        print("未解析到任何用户。退出。")
        sys.exit(1)

    results = []
    for user in users:
        result = attempt_login(user['email'], user['password'])
        results.append(result)

    # 统计结果
    total = len(results)
    success = sum(1 for r in results if r["success"])
    failed = total - success

    # 生成报告
    report_lines = [
        "🌐 *webhostmost 登录报告*",
        "===================",
        f"👥 共处理账号: {total} 个",
        f"✅ 登录成功: {success} 个",
        f"❌ 登录失败: {failed} 个",
        "===================",
        "📋 登录详情："
    ]

    for r in results:
        if r["success"]:
            days_text = f" 剩余时间 {r['days']} 天" if r.get("days") else " 剩余时间未知"
            report_lines.append(f"🟢 {r['email']} 登录成功，{days_text}")
        else:
            report_lines.append(f"🔴 {r['email']} 登录失败，原因：{r.get('reason', '未知错误')}")

    message = "\n".join(report_lines)
    print("\n" + message)

    # 发送 Telegram 通知
    send_tg_message(message)

    # 所有失败则报错退出
    if success == 0:
        print("❌ 所有账号登录失败，脚本退出。")
        sys.exit(1)


if __name__ == "__main__":
    main()
