"""
Zeabur Keep Alive Script
使用 Playwright 模拟浏览器登录，保持账户活跃
支持 Magic Link 登录（优先）和 Cookie 登录（备选）
登录成功后发送 Telegram 通知和截图，并自动更新 Cookie
"""

import os
import sys
import base64
from datetime import datetime

import requests
from nacl import encoding, public
from playwright.sync_api import sync_playwright, BrowserContext, Page

ZEABUR_DASHBOARD_URL = 'https://zeabur.com/projects'
SCREENSHOT_PATH = '/tmp/zeabur_dashboard.png'


# ==================== Telegram 通知 ====================

def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """发送 Telegram 文本消息"""
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    try:
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
        }, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f'Telegram 消息发送失败: {e}')
        return False


def send_telegram_photo(bot_token: str, chat_id: str, photo_path: str, caption: str = '') -> bool:
    """发送 Telegram 图片"""
    url = f'https://api.telegram.org/bot{bot_token}/sendPhoto'
    try:
        with open(photo_path, 'rb') as photo:
            response = requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files={'photo': photo}, timeout=60)
            response.raise_for_status()
        return True
    except Exception as e:
        print(f'Telegram 图片发送失败: {e}')
        return False


# ==================== GitHub Secret 更新 ====================

def update_github_secret(token: str, owner: str, repo: str, secret_name: str, secret_value: str):
    """更新 GitHub Repository Secret"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    
    # 获取仓库公钥
    key_url = f'https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key'
    key_response = requests.get(key_url, headers=headers, timeout=30)
    key_response.raise_for_status()
    key_data = key_response.json()
    
    # 加密
    public_key_bytes = base64.b64decode(key_data['key'])
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))
    encrypted_value = base64.b64encode(encrypted).decode('utf-8')
    
    # 更新
    update_url = f'https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}'
    requests.put(update_url, headers=headers, json={
        'encrypted_value': encrypted_value,
        'key_id': key_data['key_id'],
    }, timeout=30).raise_for_status()


# ==================== Cookie 处理 ====================

def parse_cookies(cookie_string: str) -> list:
    """解析 Cookie 字符串为 Playwright 格式"""
    cookies = []
    for cookie in cookie_string.split(';'):
        parts = cookie.strip().split('=', 1)
        if len(parts) == 2:
            cookies.append({
                'name': parts[0].strip(),
                'value': parts[1].strip(),
                'domain': '.zeabur.com',
                'path': '/',
            })
    return cookies


def format_cookies(cookies: list) -> str:
    """格式化 Cookies 为字符串"""
    return '; '.join(f"{c['name']}={c['value']}" for c in cookies if 'zeabur.com' in c.get('domain', ''))


# ==================== 登录方式 ====================

def login_with_magic_link(context: BrowserContext, magic_link: str) -> tuple[Page, bool]:
    """使用 Magic Link 登录"""
    print('🔗 尝试 Magic Link 登录...')
    page = context.new_page()
    page.set_default_timeout(60000)  # 设置 60 秒超时
    
    try:
        # Magic Link 可能需要较长时间处理认证
        page.goto(magic_link, timeout=60000, wait_until='domcontentloaded')
        page.wait_for_timeout(5000)  # 等待重定向完成
        
        # 检查是否登录成功（不在登录页）
        if '/login' not in page.url:
            print('✅ Magic Link 登录成功')
            # 跳转到控制台
            page.goto(ZEABUR_DASHBOARD_URL, wait_until='networkidle')
            page.wait_for_timeout(2000)
            return page, True
        else:
            print('❌ Magic Link 已失效或无效')
            return page, False
    except Exception as e:
        print(f'❌ Magic Link 登录失败: {e}')
        return page, False


def login_with_cookie(context: BrowserContext, cookie_string: str) -> tuple[Page, bool]:
    """使用 Cookie 登录"""
    print('🍪 尝试 Cookie 登录...')
    context.add_cookies(parse_cookies(cookie_string))
    page = context.new_page()
    
    try:
        page.goto(ZEABUR_DASHBOARD_URL, wait_until='networkidle')
        page.wait_for_timeout(2000)
        
        if '/login' not in page.url:
            print('✅ Cookie 登录成功')
            return page, True
        else:
            print('❌ Cookie 已过期')
            return page, False
    except Exception as e:
        print(f'❌ Cookie 登录失败: {e}')
        return page, False


# ==================== 主逻辑 ====================

def main():
    magic_link = os.environ.get('ZEABUR_MAGIC_LINK')
    cookie_string = os.environ.get('ZEABUR_COOKIE')
    repo_token = os.environ.get('REPO_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    tg_bot_token = os.environ.get('TG_BOT_TOKEN')
    tg_chat_id = os.environ.get('TG_CHAT_ID')

    if not magic_link and not cookie_string:
        print('❌ 错误: ZEABUR_MAGIC_LINK 和 ZEABUR_COOKIE 均未设置')
        sys.exit(1)

    print('🚀 启动浏览器...')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = None
        login_success = False
        login_method = None
        
        try:
            # 优先尝试 Cookie
            if cookie_string:
                page, login_success = login_with_cookie(context, cookie_string)
                if login_success:
                    login_method = 'Cookie'
            
            # Cookie 失效时回退到 Magic Link
            if not login_success and magic_link:
                if page:
                    page.close()
                page, login_success = login_with_magic_link(context, magic_link)
                if login_success:
                    login_method = 'Magic Link'
            
            # 登录失败
            if not login_success:
                error_msg = '❌ 所有登录方式均失败\n💡 请设置新的 ZEABUR_MAGIC_LINK'
                print(error_msg)
                if tg_bot_token and tg_chat_id:
                    send_telegram_message(tg_bot_token, tg_chat_id, error_msg)
                sys.exit(1)
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'✅ 登录成功！({login_method})\n⏰ 执行时间: {now}')
            
            # 截图
            page.screenshot(path=SCREENSHOT_PATH, full_page=False)
            print(f'📸 截图已保存')
            
            # 构建日志
            logs = [f'✅ 已访问: 控制台 ({ZEABUR_DASHBOARD_URL})']
            
            # 更新 Cookie（无论使用哪种方式登录都更新）
            new_cookie_string = format_cookies(context.cookies())
            cookie_updated = False
            if repo_token and repo and new_cookie_string:
                if new_cookie_string != cookie_string:
                    print('🔄 正在更新 Cookie...')
                    owner, repo_name = repo.split('/')
                    update_github_secret(repo_token, owner, repo_name, 'ZEABUR_COOKIE', new_cookie_string)
                    print('✅ GitHub Secret ZEABUR_COOKIE 已更新')
                    cookie_updated = True
                    logs.append(f'✅ 新 Cookie: {new_cookie_string[:20]}...{new_cookie_string[-10:]}')
                    logs.append('✅ 已自动更新 ZEABUR_COOKIE')
            
            # Telegram 通知
            if tg_bot_token and tg_chat_id:
                print('📤 正在发送 Telegram 通知...')
                # 构建格式化消息
                message = f'''🟢 <b>Zeabur 自动登录</b>

状态: ✅ 成功
登录方式: {login_method}
时间: {now}

<b>日志:</b>
''' + '\n'.join(logs)
                
                msg_sent = send_telegram_message(tg_bot_token, tg_chat_id, message)
                photo_sent = send_telegram_photo(tg_bot_token, tg_chat_id, SCREENSHOT_PATH, caption='Zeabur 控制台截图')
                if msg_sent and photo_sent:
                    print('✅ Telegram 通知已发送')
                else:
                    print('⚠️ Telegram 通知部分失败')
            else:
                print('⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过 Telegram 通知')
        
        except Exception as e:
            error_msg = f'❌ 执行失败: {str(e)}'
            print(error_msg)
            if tg_bot_token and tg_chat_id:
                send_telegram_message(tg_bot_token, tg_chat_id, error_msg)
            sys.exit(1)
        
        finally:
            browser.close()


if __name__ == '__main__':
    main()
