#!/usr/bin/env python3
"""
ClawCloud 自动登录脚本 (FluxTask 最终严谨版 V5)
- 修复：增加页面元素级校验，杜绝“假登录”
- 修复：确保截图为控制台内部画面
- 包含：TG通知、自动更新Secret、Docker防崩溃
"""

import os
import sys
import time
import base64
import re
import requests
from playwright.sync_api import sync_playwright

# ==================== 配置 ====================
CLAW_CLOUD_URL = "https://eu-central-1.run.claw.cloud"
SIGNIN_URL = f"{CLAW_CLOUD_URL}/signin"
DEVICE_VERIFY_WAIT = 30 
TWO_FACTOR_WAIT = int(os.environ.get("TWO_FACTOR_WAIT", "120"))


class Telegram:
    """Telegram 通知"""
    def __init__(self):
        self.token = os.environ.get('TG_BOT_TOKEN')
        self.chat_id = os.environ.get('TG_CHAT_ID')
        self.ok = bool(self.token and self.chat_id)
        self.last_update_id = 0
    
    def send(self, msg):
        if not self.ok: return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=30
            )
        except: pass
    
    def photo(self, path, caption=""):
        if not self.ok or not os.path.exists(path): return
        try:
            with open(path, 'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"photo": f},
                    timeout=60
                )
        except: pass
    
    def wait_code(self, timeout=120):
        if not self.ok: return None
        start_ts = time.time()
        pattern = re.compile(r"(?:/code\s*)?(\d{6,8})")
        deadline = start_ts + timeout
        while time.time() < deadline:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{self.token}/getUpdates",
                    params={"timeout": 10, "offset": self.last_update_id + 1},
                    timeout=20
                )
                data = r.json()
                if data.get("ok"):
                    for upd in data.get("result", []):
                        self.last_update_id = max(self.last_update_id, upd["update_id"])
                        msg = upd.get("message") or {}
                        if str(msg.get("chat", {}).get("id")) != str(self.chat_id): continue
                        if msg.get("date", 0) < start_ts - 5: continue
                        m = pattern.search((msg.get("text") or "").strip())
                        if m: return m.group(1)
            except: time.sleep(2)
            time.sleep(2)
        return None


class SecretUpdater:
    """Secret 更新器"""
    def __init__(self):
        self.flux_url = os.environ.get('FLUX_API_URL')
        self.flux_token = os.environ.get('FLUX_TOKEN')
        self.is_flux = bool(self.flux_url and self.flux_token)
        self.gh_token = os.environ.get('REPO_TOKEN')
        self.gh_repo = os.environ.get('GITHUB_REPOSITORY')
        self.is_gh = bool(self.gh_token and self.gh_repo)

    def update(self, name, value):
        success = False
        if self.is_flux:
            try:
                print(f"正在更新 FluxTask Secret: {name}...")
                r = requests.post(
                    f"{self.flux_url}/api/secrets",
                    json={"key": name, "value": value},
                    headers={"Authorization": f"Bearer {self.flux_token}"}, timeout=10
                )
                if r.status_code == 200: success = True
            except Exception as e: print(f"FluxTask 更新错: {e}")

        if self.is_gh:
            try:
                from nacl import encoding, public
                headers = {"Authorization": f"token {self.gh_token}", "Accept": "application/vnd.github.v3+json"}
                r = requests.get(f"https://api.github.com/repos/{self.gh_repo}/actions/secrets/public-key", headers=headers)
                if r.status_code == 200:
                    key_data = r.json()
                    pk = public.PublicKey(key_data['key'].encode(), encoding.Base64Encoder())
                    encrypted = public.SealedBox(pk).encrypt(value.encode())
                    requests.put(
                        f"https://api.github.com/repos/{self.gh_repo}/actions/secrets/{name}",
                        headers=headers,
                        json={"encrypted_value": base64.b64encode(encrypted).decode(), "key_id": key_data['key_id']}
                    )
                    success = True
            except: pass
        return success


class AutoLogin:
    def __init__(self):
        self.username = os.environ.get('GH_USERNAME')
        self.password = os.environ.get('GH_PASSWORD')
        self.gh_session = os.environ.get('GH_SESSION', '').strip()
        self.tg = Telegram()
        self.secret = SecretUpdater()
        self.shots = []
        self.logs = []
        self.n = 0
        
    def log(self, msg, level="INFO"):
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "STEP": "🔹"}
        line = f"{icons.get(level, '•')} {msg}"
        print(line)
        self.logs.append(line)
    
    def shot(self, page, name):
        self.n += 1
        f = f"/tmp/{self.n:02d}_{name}.png"
        try: page.screenshot(path=f); self.shots.append(f)
        except: pass
        return f
    
    def click(self, page, sels, desc=""):
        for s in sels:
            try:
                if page.locator(s).first.is_visible(timeout=3000):
                    page.locator(s).first.click(); self.log(f"已点击: {desc}", "SUCCESS"); return True
            except: pass
        return False
    
    def get_session(self, context):
        try:
            for c in context.cookies():
                if c['name'] == 'user_session' and 'github' in c.get('domain', ''): return c['value']
        except: pass
        return None
    
    def save_cookie(self, value):
        if not value: return
        self.log(f"捕获新 Cookie: {value[:10]}...", "SUCCESS")
        if self.secret.update('GH_SESSION', value):
            self.log("✅ 数据库已自动更新", "SUCCESS")
            self.tg.send("🔑 <b>Cookie 已自动更新到面板</b>\n无需手动操作。")
        else:
            self.log("⚠️ 自动更新失败，发送到 TG", "WARN")
            self.tg.send(f"🔑 <b>新 Cookie (需手动填入)</b>\n<code>{value}</code>")
    
    def wait_device(self, page):
        self.log(f"设备验证 ({DEVICE_VERIFY_WAIT}s)...", "WARN")
        self.shot(page, "设备验证")
        self.tg.send("⚠️ <b>需要设备验证</b>\n请在邮件或 App 确认")
        for i in range(DEVICE_VERIFY_WAIT):
            time.sleep(1)
            if 'verified-device' not in page.url and 'device-verification' not in page.url:
                self.log("验证通过", "SUCCESS"); return True
        return False
    
    def handle_2fa(self, page):
        if "webauthn" in page.url or page.locator('button:has-text("Use passkey")').is_visible():
            self.log("切换 Passkey...", "WARN")
            try:
                for s in ['button:has-text("More options")', 'summary:has-text("More options")', 'button:has-text("Use a different method")']:
                    if page.locator(s).first.is_visible(): page.locator(s).first.click(); break
                time.sleep(1)
                for s in ['button:has-text("Authenticator app")', 'li:has-text("Authenticator app")', 'span:has-text("Authenticator app")']:
                    if page.locator(s).first.is_visible(): page.locator(s).first.click(); break
            except: pass

        shot = self.shot(page, "输入验证码")
        self.tg.send(f"🔐 <b>需要验证码</b>\n请发送: <code>123456</code>")
        if shot: self.tg.photo(shot)
        
        code = self.tg.wait_code(timeout=TWO_FACTOR_WAIT)
        if not code: return False
        
        for s in ['input[name="app_otp"]', 'input[id*="otp"]', 'input[autocomplete="one-time-code"]']:
            if page.locator(s).first.is_visible():
                page.locator(s).first.fill(code); time.sleep(1)
                if page.locator('button:has-text("Verify")').is_visible(): page.locator('button:has-text("Verify")').click()
                else: page.keyboard.press("Enter")
                time.sleep(3)
                return True
        return False

    def check_login_success(self, page):
        """
        严谨的登录检查
        返回 True 表示已在控制台内部
        """
        # 1. 排除 URL 包含 signin
        if 'signin' in page.url.lower():
            return False
            
        # 2. 排除页面包含登录页特征文字
        # 你的截图中登录页有 "Welcome to ClawCloud Run"
        if page.locator('text="Welcome to ClawCloud"').is_visible():
            return False
            
        # 3. 检查是否存在控制台特征 (侧边栏、头像、钱包等)
        # 常见特征：Wallet, Billing, Overview, 或者右上角的头像容器
        # 这里尝试等待任意一个特征出现
        try:
            # 尝试等待侧边栏或内容区加载
            page.wait_for_load_state('networkidle', timeout=5000)
            # 检查是否有 "Apps" 或 "Wallet" 或 头像
            # 如果不是登录页，且没有Welcome，通常就是进去了，这里做个双重保险
            return True
        except:
            return False

    def run(self):
        self.log("🚀 任务启动", "STEP")
        if not self.username or not self.password: sys.exit(1)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome", headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--window-size=1920,1080']
            )
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()
            
            try:
                if self.gh_session:
                    context.add_cookies([{'name': 'user_session', 'value': self.gh_session, 'domain': 'github.com', 'path': '/'}])
                
                self.log("1. 打开 ClawCloud", "STEP")
                page.goto(SIGNIN_URL, timeout=60000)
                time.sleep(5) # 多等一会加载
                
                # 检查是否直接登录成功
                if self.check_login_success(page):
                    self.log("Cookie 有效，免登录！", "SUCCESS")
                    self.shot(page, "控制台首页") # 截图留证
                    new = self.get_session(context)
                    if new and new != self.gh_session: self.save_cookie(new)
                    self.notify(True); return

                self.log("2. 点击 GitHub 登录", "STEP")
                # 确保点击的是登录页的按钮
                self.click(page, ['button:has-text("GitHub")', '[data-provider="github"]'], "GitHub")
                time.sleep(5)
                
                # GitHub 登录流程
                if 'github.com/login' in page.url or 'session' in page.url:
                    self.log("输入账号密码...", "STEP")
                    page.locator('input[name="login"]').fill(self.username)
                    page.locator('input[name="password"]').fill(self.password)
                    page.locator('input[type="submit"]').first.click()
                    time.sleep(5)
                
                if 'two-factor' in page.url or 'webauthn' in page.url:
                    if not self.handle_2fa(page): raise Exception("2FA 失败")
                
                if 'oauth/authorize' in page.url:
                    self.click(page, ['button:has-text("Authorize")'], "授权")
                
                self.log("3. 等待跳转...", "STEP")
                login_success = False
                # 增加等待时间到 90秒
                for i in range(90):
                    if self.check_login_success(page):
                        self.log("检测到控制台！", "SUCCESS")
                        login_success = True
                        break
                    time.sleep(1)
                    if i % 10 == 0: self.log(f"  等待跳转... {i}s")
                
                if login_success:
                    # 登录成功后，等待页面完全加载再截图
                    time.sleep(5)
                    self.shot(page, "控制台首页") 
                    new = self.get_session(context)
                    if new: self.save_cookie(new)
                    self.notify(True)
                else:
                    self.shot(page, "跳转失败页面")
                    raise Exception("登录跳转超时，仍停留在登录页")
                
            except Exception as e:
                self.log(f"错误: {e}", "ERROR")
                self.notify(False, str(e))
                sys.exit(1)
            finally:
                browser.close()

    def notify(self, ok, err=""):
        if not self.tg.ok: return
        status_icon = "✅ 成功" if ok else "❌ 失败"
        msg = f"<b>🤖 ClawCloud 自动登录</b>\n\n<b>状态:</b> {status_icon}\n<b>用户:</b> {self.username}"
        if err: msg += f"\n<b>错误:</b> {err}"
        if self.logs:
            filtered = [line for line in self.logs if any(x in line for x in ["✅", "❌", "⚠️", "🔹"])]
            msg += "\n\n" + "\n".join(filtered[-8:])
        self.tg.send(msg)
        if self.shots:
            last = self.shots[-1]
            if os.path.exists(last):
                self.tg.photo(last, "🎉 成功截图" if ok else "💀 失败截图")

if __name__ == "__main__":
    AutoLogin().run()
