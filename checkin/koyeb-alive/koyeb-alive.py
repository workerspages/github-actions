import os
import requests
import json
import time
import logging
from typing import List, Dict, Tuple, Any, Optional
from datetime import datetime, timezone, timedelta

# --- 常量定义 ---
KOYEB_PROFILE_URL = "https://app.koyeb.com/v1/account/profile"
REQUEST_TIMEOUT = 30  # 请求超时，单位：秒
BEIJING_TZ = timezone(timedelta(hours=8))

# --- 日志配置 ---
class BeijingTimeFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, BEIJING_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime(self.datefmt)

# 应用北京时间格式化器
handler = logging.StreamHandler()
handler.setFormatter(BeijingTimeFormatter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

logging.basicConfig(level=logging.INFO, handlers=[handler])

# --- 账户加载/验证函数 ---
def validate_and_load_accounts() -> List[Dict[str, str]]:
    """
    从环境变量 KOYEB_LOGIN 加载账户信息。
    格式: "email1:PAT1\nemail2:PAT2"
    """
    koyeb_login_env = os.getenv("KOYEB_LOGIN")
    if not koyeb_login_env:
        logging.error(f"❌ KOYEB_LOGIN 变量未配置，脚本无法继续执行")
        raise ValueError("必须配置 KOYEB_LOGIN 环境变量")

    accounts = []
    lines = koyeb_login_env.strip().split('\n') # 按行分割，并处理空行
    
    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            logging.warning(f"⚠️ 跳过无效或空行: {line}")
            continue

        try:
            email, pat = line.split(':', 1) # 只按第一个冒号分割，防止PAT中包含冒号被误分
            accounts.append({
                'email': email.strip(),
                'pat': pat.strip()
            })
        except ValueError:
            logging.error(f"⚠️ KOYEB_LOGIN 行格式错误，应为 email:PAT -> {line}")
            continue
            
    if not accounts:
        raise ValueError("KOYEB_LOGIN 环境变量未包含任何有效账户信息")
    
    return accounts

# --- Telegram 发送函数 ---
def send_tg_message(message: str) -> Optional[Dict[str, Any]]:
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token or not chat_id:
        logging.warning("⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过发送 Telegram 消息。")
        return None

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"❌ 发送 Telegram 消息时发生HTTP错误: {http_err}")
        logging.error(f"❌ 响应内容: {http_err.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ 发送 Telegram 消息失败: {e}")
        return None

# --- 账户验证函数 ---
def verify_koyeb_account_status(email: str, pat: str) -> Tuple[bool, str]:
    """
    使用 PAT 调用 /v1/account/profile 端点，并验证账户状态。
    """
    if not email or not pat:
        return False, "邮箱或个人访问令牌 (PAT) 为空"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {pat}", 
        "User-Agent": "KoyebAccountStatusChecker/1.0"
    }

    try:
        response = requests.get(
            KOYEB_PROFILE_URL,  
            headers=headers,  
            timeout=REQUEST_TIMEOUT,
        )
        
        # 检查 HTTP 状态码
        if response.status_code == 401 or response.status_code == 403:
             return False, "验证失败：PAT 无效或已过期。"
        
        response.raise_for_status() # 抛出非 2xx 状态码错误

        # 解析并验证返回的 JSON 数据
        profile_data = response.json() 
        user_info = profile_data.get('user', {})
        returned_email = user_info.get('email', '')
        flags = user_info.get('flags', [])
        email_validated = user_info.get('email_validated', False)
        
        # 严格验证逻辑
        if returned_email.lower() != email.lower():
            return False, f"验证失败：API返回邮箱({returned_email})与提供邮箱不匹配。"
        
        is_active = "ACTIVE" in flags
        
        if is_active and email_validated:
            return True, "活跃且邮箱已验证"
        elif not is_active:
            return False, f"原因: 非活跃 (Flags: {', '.join(flags)})"
        elif not email_validated:
            return False, "原因: 邮箱未验证"
        else:
            return False, f"原因: 未知账户: {user_info}"


    except requests.exceptions.HTTPError as http_err:
        try:
            error_data = http_err.response.json()
            error_message = error_data.get('error', http_err.response.text)
            return False, f"原因: API错误 (状态码 {http_err.response.status_code}): {error_message}"
        except json.JSONDecodeError:
            return False, f"原因: HTTP错误 (状态码 {http_err.response.status_code}): {http_err.response.text}"
    except requests.exceptions.Timeout:
        return False, "原因: 请求超时"
    except requests.exceptions.RequestException as e:
        return False, f"原因: 网络请求异常: {e}"
    except Exception as e:
        return False, f"原因: 处理响应时发生异常: {e}"
        
def main():
    try:
        koyeb_accounts = validate_and_load_accounts()
        
        results = []
        current_time_dt = datetime.now(BEIJING_TZ)
        current_time = current_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        total_accounts = len(koyeb_accounts)
        success_count = 0

        for index, account in enumerate(koyeb_accounts, 1):
            email = account.get('email', '').strip()
            pat = account.get('pat', '')

            if not email or not pat:
                logging.warning(f"⚠️ 第 {index}/{total_accounts} 个账户信息不完整，已跳过")
                results.append(f"账户: 未提供邮箱\n状态: ❌ 信息不完整\n")
                continue

            logging.info(f"🚀 正在处理第 {index}/{total_accounts} 个账户: {email}")
            time.sleep(10)

            try:
                # 调用验证函数
                success, message = verify_koyeb_account_status(email, pat)
                if success:
                    status_line = f"状态: ✅ {message}"
                    success_count += 1
                else:
                    status_line = f"状态: ❌ 验证失败\n  {message}"
            except Exception as e:
                logging.error(f"❌ 处理账户 {email} 时发生未知异常: {e}")
                status_line = f"状态: ❌ 验证失败\n  执行时发生未知异常 - {e}"

            results.append(f"账户: `{email}`\n{status_line}\n")

        summary = f"📊 总计: {total_accounts} 个账户\n✅ 成功: {success_count} 个 | ❌ 失败: {total_accounts - success_count} 个"
        report_body = "".join(results)
        tg_message = (
            f"🤖 *Koyeb 账户状态报告* 🤖\n"
            f"=====================\n"
            f"⏰ 日期: {current_time}\n"
            f"{summary}\n"
            f"---------------------------\n"
            f"{report_body}"
        )

        logging.info("📊 --- 报告预览 ---\n" + tg_message)
        send_tg_message(tg_message)
        logging.info("🎉 脚本执行完毕。")

        if success_count == 0 and total_accounts > 0:
            logging.error("❌ 所有账户验证失败，脚本将以非零状态码退出")
            import sys
            sys.exit(1)

    except Exception as e:
        error_message = f"❌ 程序初始化失败: {e}"
        logging.error(error_message)
        send_tg_message(error_message)
        import sys
        sys.exit(1)
            
if __name__ == "__main__":
    main()
