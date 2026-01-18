#!/usr/bin/env python3
"""
ClawCloud 自动登录脚本 (最终完美版 V3)
- 修复 Passkey 页面 "Authenticator app" 按钮点击失效问题
- 增强选择器覆盖范围
- 保持 Docker 环境兼容性
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
DEVICE_VERIFY_WAIT = 30  # Mobile验证 默认等 30 秒
TWO_FACTOR_WAIT = int(os.environ.get("TWO_FACTOR_WAIT", "120"))  # 2FA验证 默认等 120 秒


class Telegram:
    """Telegram 通知"""
    
    def __init__(self):
        self.token = os.environ.get('TG_BOT_TOKEN')
        self.chat_id = os.environ.get('TG_CHAT_ID')
        self.ok = bool(self.token and self.chat_id)
    
    def send(self, msg):
        if not self.ok:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=30
            )
        except:
            pass
    
    def photo(self, path, caption=""):
        if not self.ok or not os.path.exists(path):
            return
        try:
            with open(path, 'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"photo": f},
                    timeout=60
                )
        except:
            pass
    
    def flush_updates(self):
        """刷新 offset 到最新，避免读到旧消息"""
        if not self.ok:
            return 0
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                params={"timeout": 0},
                timeout=10
            )
            data = r.json()
            if data.get("ok") and data.get("result"):
                return data["result"][-1]["update_id"] + 1
        except:
            pass
        return 0
    
    def wait_code(self, timeout=120):
        """
        等待你在 TG 里发 /code 123456
        只接受来自 TG_CHAT_ID 的消息
        """
        if not self.ok:
            return None
        
        # 先刷新 offset，避免读到旧的 /code
        offset = self.flush_updates()
        deadline = time.time() + timeout
        pattern = re.compile(r"^/code\s+(\d{6,8})$")  # 6位TOTP 或 8位恢复码也行
        
        while time.time() < deadline:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{self.token}/getUpdates",
                    params={"timeout": 20, "offset": offset},
                    timeout=30
                )
                data = r.json()
                if not data.get("ok"):
                    time.sleep(2)
                    continue
                
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    chat = msg.get("chat") or {}
                    if str(chat.get("id")) != str(self.chat_id):
                        continue
                    
                    text = (msg.get("text") or "").strip()
                    m = pattern.match(text)
                    if m:
                        return m.group(1)
            
            except Exception:
                pass
            
            time.sleep(2)
        
        return None


class SecretUpdater:
    """Secret 更新器 - 优先使用内部 API，回退到 GitHub API"""
    
    def __init__(self):
        # 内部 API 模式（私有化部署）
        self.flux_token = os.environ.get('FLUX_TOKEN')
        self.flux_url = os.environ.get('FLUX_API_URL')
        self.script_id = os.environ.get('FLUX_SCRIPT_ID')
        self.use_internal = bool(self.flux_token and self.flux_url and self.script_id)
        
        # GitHub API 模式（原版）
        self.gh_token = os.environ.get('REPO_TOKEN')
        self.repo = os.environ.get('GITHUB_REPOSITORY')
        self.use_github = bool(self.gh_token and self.repo)
        
        if self.use_internal:
            print("✅ Secret 自动更新已启用（内部 API 模式）")
        elif self.use_github:
            print("✅ Secret 自动更新已启用（GitHub API 模式）")
        else:
            print("⚠️ Secret 自动更新未启用")
        
        self.ok = self.use_internal or self.use_github
    
    def update(self, name, value):
        if not self.ok:
            return False
        
        # 优先使用内部 API
        if self.use_internal:
            return self._update_internal(name, value)
        
        # 回退到 GitHub API
        return self._update_github(name, value)
    
    def _update_internal(self, name, value):
        """使用内部 API 更新任务独享 Secrets"""
        try:
            r = requests.put(
                f"{self.flux_url}/api/scripts/{self.script_id}/secrets/{name}",
                json={"value": value},
                headers={"Authorization": f"Bearer {self.flux_token}"},
                timeout=30
            )
            return r.status_code == 200
        except Exception as e:
            print(f"内部 API 更新失败: {e}")
            return False
    
    def _update_github(self, name, value):
        """使用 GitHub API 更新仓库 Secrets（原版逻辑）"""
        try:
            try:
                from nacl import encoding, public
            except ImportError:
                print("❌ 缺少 PyNaCl 库，无法加密 Secret，请在依赖中添加 PyNaCl")
                return False
            
            headers = {
                "Authorization": f"token {self.gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            r = requests.get(
                f"https://api.github.com/repos/{self.repo}/actions/secrets/public-key",
                headers=headers, timeout=30
            )
            if r.status_code != 200:
                return False
            
            key_data = r.json()
            pk = public.PublicKey(key_data['key'].encode(), encoding.Base64Encoder())
            encrypted = public.SealedBox(pk).encrypt(value.encode())
            
            r = requests.put(
                f"https://api.github.com/repos/{self.repo}/actions/secrets/{name}",
                headers=headers,
                json={"encrypted_value": base64.b64encode(encrypted).decode(), "key_id": key_data['key_id']},
                timeout=30
            )
            return r.status_code in [201, 204]
        except Exception as e:
            print(f"更新 Secret 失败: {e}")
            return False


class AutoLogin:
    """自动登录"""
    
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
        # 使用 /tmp 目录，避免权限问题
        f = f"/tmp/{self.n:02d}_{name}.png" 
        try:
            page.screenshot(path=f)
            self.shots.append(f)
        except:
            pass
        return f
    
    def click(self, page, sels, desc=""):
        for s in sels:
            try:
                el = page.locator(s).first
                if el.is_visible(timeout=3000):
                    el.click()
                    self.log(f"已点击: {desc}", "SUCCESS")
                    return True
            except:
                pass
        return False
    
    def get_session(self, context):
        """提取 Session Cookie"""
        try:
            for c in context.cookies():
                if c['name'] == 'user_session' and 'github' in c.get('domain', ''):
                    return c['value']
        except:
            pass
        return None
    
    def save_cookie(self, value):
        """保存新 Cookie"""
        if not value:
            return
        
        self.log(f"新 Cookie: {value[:15]}...{value[-8:]}", "SUCCESS")
        
        # 自动更新 Secret
        if self.secret.update('GH_SESSION', value):
            self.log("已自动更新 GH_SESSION", "SUCCESS")
            self.tg.send("🔑 <b>Cookie 已自动更新</b>\n\nGH_SESSION 已保存")
        else:
            # 通过 Telegram 发送
            self.tg.send(f"""🔑 <b>新 Cookie</b>

请更新 Secret <b>GH_SESSION</b>:
<code>{value}</code>""")
            self.log("已通过 Telegram 发送 Cookie", "SUCCESS")
    
    def wait_device(self, page):
        """等待设备验证"""
        self.log(f"需要设备验证，等待 {DEVICE_VERIFY_WAIT} 秒...", "WARN")
        self.shot(page, "设备验证")
        
        self.tg.send(f"""⚠️ <b>需要设备验证</b>

请在 {DEVICE_VERIFY_WAIT} 秒内批准：
1️⃣ 检查邮箱点击链接
2️⃣ 或在 GitHub App 批准""")
        
        if self.shots:
            self.tg.photo(self.shots[-1], "设备验证页面")
        
        for i in range(DEVICE_VERIFY_WAIT):
            time.sleep(1)
            if i % 5 == 0:
                self.log(f"  等待... ({i}/{DEVICE_VERIFY_WAIT}秒)")
                url = page.url
                if 'verified-device' not in url and 'device-verification' not in url:
                    self.log("设备验证通过！", "SUCCESS")
                    self.tg.send("✅ <b>设备验证通过</b>")
                    return True
                try:
                    page.reload(timeout=10000)
                    page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    pass
        
        if 'verified-device' not in page.url:
            return True
        
        self.log("设备验证超时", "ERROR")
        self.tg.send("❌ <b>设备验证超时</b>")
        return False
    
    def wait_two_factor_mobile(self, page):
        """等待 GitHub Mobile 两步验证批准"""
        self.log(f"需要两步验证（Mobile），等待 {TWO_FACTOR_WAIT} 秒...", "WARN")
        
        shot = self.shot(page, "两步验证_mobile")
        self.tg.send(f"""⚠️ <b>需要两步验证（GitHub Mobile）</b>

请打开手机 GitHub App 批准本次登录。
等待时间：{TWO_FACTOR_WAIT} 秒""")
        if shot:
            self.tg.photo(shot, "两步验证页面（数字在图里）")
        
        for i in range(TWO_FACTOR_WAIT):
            time.sleep(1)
            url = page.url
            if "github.com/sessions/two-factor/" not in url:
                self.log("两步验证通过！", "SUCCESS")
                self.tg.send("✅ <b>两步验证通过</b>")
                return True
            
            if "github.com/login" in url:
                self.log("流程中断，回到了登录页", "ERROR")
                return False
            
            if i % 10 == 0 and i != 0:
                self.log(f"  等待... ({i}/{TWO_FACTOR_WAIT}秒)")
        
        self.log("两步验证超时", "ERROR")
        return False
    
    def handle_2fa_code_input(self, page):
        """处理 TOTP 验证码输入 (增强版：适配 More options)"""
        self.log("进入验证码处理流程...", "STEP")
        
        # ================== 处理 Passkey / WebAuthn 页面 ==================
        # 检测是否在 Passkey 页面
        if "webauthn" in page.url or page.locator('button:has-text("Use passkey")').is_visible():
            self.log("检测到 Passkey 页面，尝试切换...", "WARN")
            try:
                # 1. 查找 "More options" 或 "Use a different method" 按钮
                # GitHub 界面这里变化多端，列出所有可能性
                switchers = [
                    'button:has-text("More options")',
                    'summary:has-text("More options")', 
                    '[aria-label="Show more authentication options"]',
                    'button:has-text("Use a different method")',
                    'a:has-text("Use a different method")',
                    '[aria-label="Select a different method"]'
                ]
                
                clicked_switch = False
                for sel in switchers:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=1000):
                            el.click()
                            time.sleep(1)
                            clicked_switch = True
                            self.log(f"已点击切换按钮: {sel}", "SUCCESS")
                            break
                    except:
                        pass
                
                # 2. 点击 "Authenticator app"
                # 注意：必须匹配你的截图中的文字 "Authenticator app"
                if clicked_switch:
                    app_options = [
                        'button:has-text("Authenticator app")',
                        'span:has-text("Authenticator app")',
                        'div:has-text("Authenticator app")',
                        'li:has-text("Authenticator app")',
                        'a:has-text("Authenticator app")',
                        'button:has-text("Authentication app")', # 旧文案备份
                    ]
                    for sel in app_options:
                        try:
                            el = page.locator(sel).first
                            if el.is_visible(timeout=2000):
                                el.click()
                                time.sleep(3)
                                page.wait_for_load_state('networkidle')
                                self.log("已切换到验证码 App 模式", "SUCCESS")
                                break
                        except:
                            pass
            except Exception as e:
                self.log(f"切换验证方式失败: {e}", "WARN")
        # ====================================================================

        shot = self.shot(page, "两步验证_code")
        
        self.tg.send(f"""🔐 <b>需要验证码</b>
请在 TG 发送：<code>/code 123456</code>
等待：{TWO_FACTOR_WAIT} 秒""")
        
        if shot: self.tg.photo(shot)
        
        code = self.tg.wait_code(timeout=TWO_FACTOR_WAIT)
        if not code:
            self.log("等待验证码超时", "ERROR")
            return False
        
        self.log("收到验证码，正在填入...", "SUCCESS")
        
        # 常见 OTP 输入框
        selectors = [
            'input[autocomplete="one-time-code"]', 
            'input[name="app_otp"]', 
            'input#app_totp', 
            'input[id*="otp"]',
            'input[type="text"][maxlength="6"]' # 兜底策略
        ]
        
        for sel in selectors:
            try:
                el = page.locator(sel).first
                # 等待输入框出现，最多等 3 秒
                if el.is_visible(timeout=3000):
                    el.fill(code)
                    time.sleep(1)
                    
                    verify_btn = page.locator('button:has-text("Verify")').first
                    if verify_btn.is_visible(timeout=1000):
                        verify_btn.click()
                    else:
                        page.keyboard.press("Enter")
                    
                    time.sleep(3)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    
                    if "two-factor" not in page.url and "webauthn" not in page.url:
                        self.log("验证码通过", "SUCCESS")
                        return True
            except:
                pass
        
        self.log("验证失败 (未找到输入框或验证码错误)", "ERROR")
        return False
    
    def login_github(self, page, context):
        """登录 GitHub"""
        self.log("登录 GitHub...", "STEP")
        self.shot(page, "github_登录页")
        
        try:
            page.locator('input[name="login"]').fill(self.username)
            page.locator('input[name="password"]').fill(self.password)
            page.locator('input[type="submit"], button[type="submit"]').first.click()
        except Exception as e:
            self.log(f"输入失败: {e}", "ERROR")
            return False
        
        time.sleep(3)
        page.wait_for_load_state('networkidle', timeout=30000)
        self.shot(page, "github_登录后")
        
        url = page.url
        self.log(f"当前: {url}")
        
        # 设备验证
        if 'verified-device' in url or 'device-verification' in url:
            if not self.wait_device(page): return False
            time.sleep(2)
        
        # 2FA 处理
        if 'two-factor' in page.url or 'webauthn' in page.url:
            # 优先检查是否是 Mobile 验证页面
            if 'two-factor/mobile' in page.url:
                if not self.wait_two_factor_mobile(page): return False
            else:
                # 其他情况（包括 Passkey, SMS, TOTP）都交给通用处理
                if not self.handle_2fa_code_input(page): return False
        
        return True
    
    def oauth(self, page):
        """处理 OAuth"""
        if 'github.com/login/oauth/authorize' in page.url:
            self.log("处理 OAuth...", "STEP")
            self.shot(page, "oauth")
            self.click(page, ['button[name="authorize"]', 'button:has-text("Authorize")'], "授权")
            time.sleep(3)
            page.wait_for_load_state('networkidle', timeout=30000)
    
    def wait_redirect(self, page, wait=60):
        """等待重定向"""
        self.log("等待重定向...", "STEP")
        for i in range(wait):
            url = page.url
            if 'claw.cloud' in url and 'signin' not in url.lower():
                self.log("重定向成功！", "SUCCESS")
                return True
            if 'github.com/login/oauth/authorize' in url:
                self.oauth(page)
            time.sleep(1)
            if i % 10 == 0: self.log(f"  等待... ({i}s)")
        return False
    
    def keepalive(self, page):
        """保活"""
        self.log("保活...", "STEP")
        for url in [f"{CLAW_CLOUD_URL}/", f"{CLAW_CLOUD_URL}/apps"]:
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle', timeout=15000)
                time.sleep(2)
            except: pass
        self.shot(page, "完成")
    
    def notify(self, ok, err=""):
        if not self.tg.ok: return
        msg = f"<b>🤖 ClawCloud 自动登录</b>\n\n<b>状态:</b> {'✅ 成功' if ok else '❌ 失败'}\n<b>用户:</b> {self.username}"
        if err: msg += f"\n<b>错误:</b> {err}"
        msg += "\n\n" + "\n".join(self.logs[-6:])
        self.tg.send(msg)
        if self.shots:
            self.tg.photo(self.shots[-1] if ok else self.shots[-1], "截图")
    
    def run(self):
        self.log("🚀 任务启动", "STEP")
        
        if not self.username or not self.password:
            self.log("缺少 GH_USERNAME 或 GH_PASSWORD", "ERROR")
            sys.exit(1)
        
        with sync_playwright() as p:
            # ================= 关键修改：Docker 兼容启动参数 =================
            browser = p.chromium.launch(
                channel="chrome",  # 强制使用容器内的 Chrome
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage', # 防止内存崩溃
                    '--disable-gpu',
                    '--window-size=1920,1080'
                ]
            )
            # ============================================================
            
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()
            
            try:
                # 预加载 Cookie
                if self.gh_session:
                    try:
                        context.add_cookies([
                            {'name': 'user_session', 'value': self.gh_session, 'domain': 'github.com', 'path': '/'},
                            {'name': 'logged_in', 'value': 'yes', 'domain': 'github.com', 'path': '/'}
                        ])
                        self.log("已加载 Session Cookie", "SUCCESS")
                    except: pass
                
                # 1. 访问
                self.log("步骤1: 打开 ClawCloud", "STEP")
                page.goto(SIGNIN_URL, timeout=60000)
                page.wait_for_load_state('networkidle', timeout=30000)
                time.sleep(2)
                
                if 'signin' not in page.url.lower():
                    self.log("Cookie 有效，已登录！", "SUCCESS")
                    self.keepalive(page)
                    new = self.get_session(context)
                    if new and new != self.gh_session: self.save_cookie(new)
                    self.notify(True)
                    return
                
                # 2. 点击 GitHub
                self.log("步骤2: 点击 GitHub", "STEP")
                if not self.click(page, ['button:has-text("GitHub")', 'a:has-text("GitHub")', '[data-provider="github"]'], "GitHub"):
                    raise Exception("找不到 GitHub 登录按钮")
                
                time.sleep(3)
                url = page.url
                
                # 3. 登录
                if 'github.com/login' in url or 'github.com/session' in url:
                    if not self.login_github(page, context):
                        raise Exception("GitHub 登录流程失败")
                elif 'github.com/login/oauth/authorize' in url:
                    self.oauth(page)
                
                # 4. 重定向
                if not self.wait_redirect(page):
                    raise Exception("重定向回 ClawCloud 失败")
                
                # 5. 保活
                self.keepalive(page)
                
                # 6. 保存 Cookie
                new = self.get_session(context)
                if new: self.save_cookie(new)
                
                self.notify(True)
                
            except Exception as e:
                self.log(f"异常: {e}", "ERROR")
                import traceback
                traceback.print_exc()
                self.notify(False, str(e))
                sys.exit(1)
            finally:
                browser.close()

if __name__ == "__main__":
    AutoLogin().run()
