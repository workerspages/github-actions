#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本
变量名：LEAFLOW_ACCOUNTS
变量值：邮箱1:密码1,邮箱2:密码2,邮箱3:密码3
"""

import os
import time
import logging
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        if not self.email or not self.password:
            raise ValueError("邮箱和密码不能为空")
        self.setup_driver()

    def setup_driver(self):
        """设置Chrome驱动选项"""
        chrome_options = Options()
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def close_popup(self):
        """关闭初始弹窗"""
        try:
            logger.info("尝试关闭初始弹窗...")
            time.sleep(3)
            actions = ActionChains(self.driver)
            actions.move_by_offset(10, 10).click().perform()
            time.sleep(2)
            return True
        except Exception:
            return False

    def wait_for_element_clickable(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def wait_for_element_present(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def login(self):
        """执行登录流程"""
        logger.info("开始登录流程")
        self.driver.get("https://leaflow.net/login")
        time.sleep(5)
        self.close_popup()

        # 输入邮箱
        email_selectors = [
            "input[type='text']", "input[type='email']",
            "input[placeholder*='邮箱']", "input[placeholder*='邮件']",
            "input[placeholder*='email']", "input[name='email']",
            "input[name='username']"
        ]
        email_input = None
        for sel in email_selectors:
            try:
                email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, sel, 5)
                break
            except:
                continue
        if not email_input:
            raise Exception("找不到邮箱输入框")
        email_input.clear()
        email_input.send_keys(self.email)
        time.sleep(2)

        # 输入密码
        password_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='password']", 10)
        password_input.clear()
        password_input.send_keys(self.password)
        time.sleep(1)

        # 点击登录
        login_btn_selectors = [
            "//button[contains(text(), '登录')]", "//button[contains(text(), 'Login')]",
            "//button[@type='submit']", "button[type='submit']"
        ]
        login_btn = None
        for sel in login_btn_selectors:
            try:
                if sel.startswith("//"):
                    login_btn = self.wait_for_element_clickable(By.XPATH, sel, 5)
                else:
                    login_btn = self.wait_for_element_clickable(By.CSS_SELECTOR, sel, 5)
                break
            except:
                continue
        if not login_btn:
            raise Exception("找不到登录按钮")
        login_btn.click()

        # 等待登录完成
        WebDriverWait(self.driver, 20).until(
            lambda d: "dashboard" in d.current_url or "workspaces" in d.current_url or "login" not in d.current_url
        )
        return True

    def get_balance(self):
        """获取当前账号的总余额"""
        self.driver.get("https://leaflow.net/dashboard")
        time.sleep(3)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        balance_selectors = [
            "//*[contains(text(), '¥') or contains(text(), '￥') or contains(text(), '元')]",
            "//*[contains(@class, 'balance')]", "//*[contains(@class, 'amount')]"
        ]
        import re
        for sel in balance_selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for e in elems:
                    txt = e.text.strip()
                    if any(c.isdigit() for c in txt) and ('¥' in txt or '￥' in txt or '元' in txt):
                        nums = re.findall(r'\d+\.?\d*', txt)
                        if nums:
                            return f"{nums[0]}元"
            except:
                continue
        return "未知"

    def wait_for_checkin_page_loaded(self, max_retries=3, wait_time=20):
        for attempt in range(max_retries):
            time.sleep(wait_time)
            indicators = [
                "button.checkin-btn", "//button[contains(text(), '立即签到')]",
                "//*[contains(text(), '每日签到')]"
            ]
            for ind in indicators:
                try:
                    if ind.startswith("//"):
                        el = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, ind))
                        )
                    else:
                        el = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ind))
                        )
                    if el.is_displayed():
                        return True
                except:
                    continue
        return False

    def find_and_click_checkin_button(self):
        """查找并点击签到按钮"""
        time.sleep(5)
        selectors = [
            "button.checkin-btn", "//button[contains(text(), '立即签到')]",
            "//button[contains(@class, 'checkin')]"
        ]
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, sel))
                    )
                else:
                    btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                if "已签到" in btn.text or not btn.is_enabled():
                    return "already_checked_in"
                btn.click()
                return True
            except:
                continue
        return False

    def checkin(self):
        self.driver.get("https://checkin.leaflow.net")
        if not self.wait_for_checkin_page_loaded():
            raise Exception("签到页面加载失败")
        res = self.find_and_click_checkin_button()
        if res == "already_checked_in":
            return "今日已签到"
        elif res is True:
            time.sleep(5)
            return self.get_checkin_result()
        else:
            raise Exception("找不到签到按钮")

    def get_checkin_result(self):
        time.sleep(3)
        success_selectors = [".alert-success", ".message", ".toast"]
        for sel in success_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el.text.strip()
            except:
                continue
        body = self.driver.find_element(By.TAG_NAME, "body").text
        for kw in ["成功", "获得", "恭喜", "已签到"]:
            if kw in body:
                for line in body.split('\n'):
                    if kw in line and len(line) < 100:
                        return line.strip()
        return "签到完成"

    def run(self):
        try:
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                return True, result, balance
        except Exception as e:
            return False, f"失败: {e}", "未知"
        finally:
            if self.driver:
                self.driver.quit()

class MultiAccountManager:
    """多账号管理器 - 支持 Telegram 和 Pushplus 通知"""

    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.pushplus_token = os.getenv('PUSHPLUS_TOKEN', '')
        self.accounts = self.load_accounts()

    def load_accounts(self):
        accounts = []
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            for pair in accounts_str.split(','):
                if ':' in pair:
                    email, pwd = pair.split(':', 1)
                    accounts.append({'email': email.strip(), 'password': pwd.strip()})
        else:
            em = os.getenv('LEAFLOW_EMAIL', '').strip()
            pw = os.getenv('LEAFLOW_PASSWORD', '').strip()
            if em and pw:
                accounts.append({'email': em, 'password': pw})
        if not accounts:
            raise ValueError("未找到有效的账号配置")
        return accounts

    def send_pushplus(self, message: str, title: str = "Leaflow自动签到通知"):
        """通过 Pushplus 发送通知"""
        if not self.pushplus_token:
            logger.info("Pushplus Token 未配置，跳过 Pushplus 通知")
            return
        try:
            url = "http://www.pushplus.plus/send"
            payload = {
                "token": self.pushplus_token,
                "title": title,
                "content": message,
                "template": "html"
            }
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                logger.info("Pushplus 通知发送成功")
            else:
                logger.error(f"Pushplus 通知失败: {data}")
        except Exception as e:
            logger.error(f"发送 Pushplus 通知时出错: {e}")

    def send_notification(self, results):
        """发送汇总通知到 Telegram 和 Pushplus"""
        # 构建消息
        success_count = sum(1 for _, ok, _, _ in results if ok)
        total = len(results)
        date_str = datetime.now().strftime("%Y/%m/%d")
        msg = f"🎁 Leaflow自动签到通知\n📊 成功: {success_count}/{total}\n📅 时间: {date_str}\n\n"
        for email, ok, res, bal in results:
            masked = email[:3] + "***" + email[email.find("@"):]
            if ok:
                msg += f"账号：{masked}\n✅ {res}\n💰 余额：{bal}\n\n"
            else:
                msg += f"账号：{masked}\n❌ {res}\n\n"

        # Telegram
        if self.telegram_bot_token and self.telegram_chat_id:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {"chat_id": self.telegram_chat_id, "text": msg, "parse_mode": "HTML"}
            try:
                requests.post(url, data=data, timeout=10)
                logger.info("Telegram 通知发送成功")
            except Exception as e:
                logger.error(f"发送 Telegram 通知失败: {e}")
        else:
            logger.info("Telegram 配置未设置，跳过 Telegram 通知")

        # Pushplus
        self.send_pushplus(msg)

    def run_all(self):
        results = []
        for i, acc in enumerate(self.accounts, 1):
            logger.info(f"开始第 {i}/{len(self.accounts)} 个账号签到")
            checker = LeaflowAutoCheckin(acc['email'], acc['password'])
            ok, res, bal = checker.run()
            results.append((acc['email'], ok, res, bal))
            if i < len(self.accounts):
                time.sleep(5)
        self.send_notification(results)
        return all(ok for _, ok, _, _ in results), results

def main():
    try:
        mgr = MultiAccountManager()
        overall_ok, details = mgr.run_all()
        if overall_ok:
            logger.info("✅ 所有账号签到成功")
            exit(0)
        else:
            logger.warning("⚠️ 部分账号签到失败")
            exit(0)
    except Exception as e:
        logger.error(f"❌ 脚本执行出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
