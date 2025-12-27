#!/usr/bin/env python3
"""
Leaflow 自动签到脚本
支持单账号和多账号签到
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LeaflowAutoCheckin:
    # 配置class类常量
    LOGIN_URL = "https://leaflow.net/login"
    CHECKIN_URL = "https://checkin.leaflow.net"
    WAIT_TIME_AFTER_LOGIN = 15  # 登录后等待的秒数
    WAIT_TIME_AFTER_CHECKIN_CLICK = 5  # 点击签到后等待的秒数
    RETRY_WAIT_TIME_PAGE_LOAD = 15 # 签到页面加载每次重试等待时间
    RETRY_COUNT_PAGE_LOAD = 3 # 签到页面加载重试次数

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.telegram_bot_token = os.getenv('TG_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TG_CHAT_ID', '')
        
        if not self.email or not self.password:
            raise ValueError("邮箱和密码不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项"""
        chrome_options = Options()
        
        # GitHub Actions环境配置
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
        
        # 通用配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def close_popup(self):
        """关闭初始弹窗"""
        try:
            logger.info("👉 尝试关闭初始弹窗...")
            time.sleep(3)  # 等待弹窗加载
            
            # 尝试点击页面左上角空白处关闭弹窗
            try:
                actions = ActionChains(self.driver)
                # 点击页面左上角(10,10)位置
                actions.move_by_offset(10, 10).click().perform()
                logger.info("✅ 关闭弹窗成功")
                time.sleep(2)
                return True
            except:
                pass

            return False
            
        except Exception as e:
            logger.warning(f"❌ 关闭弹窗时出错: {e}")
            return False
    
    def wait_for_element_clickable(self, by, value, timeout=10):
        """等待元素可点击"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=10):
        """等待元素出现"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def login(self):
        """执行登录流程"""
        logger.info(f"🔑 开始登录流程")
        
        # 访问登录页面
        self.driver.get(self.LOGIN_URL)
        time.sleep(5)
        
        # 关闭弹窗
        self.close_popup()
        
        # 输入邮箱
        try:
            logger.info("🔍 查找邮箱输入框...")
            time.sleep(2)
            
            # 尝试多种选择器找到邮箱输入框
            email_selectors = [
                "input[type='text']",
                "input[type='email']", 
                "input[placeholder*='邮箱']",
                "input[placeholder*='邮件']",
                "input[placeholder*='email']",
                "input[name='email']",
                "input[name='username']"
            ]
            
            email_input = None
            for selector in email_selectors:
                try:
                    email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                    logger.info(f"✅ 找到邮箱输入框")
                    break
                except:
                    continue
            
            if not email_input:
                raise Exception("❌ 找不到邮箱输入框")
            
            # 清除并输入邮箱
            email_input.clear()
            email_input.send_keys(self.email)
            logger.info("✅ 邮箱输入完成")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ 输入邮箱时出错: {e}")
            # 尝试使用JavaScript直接设置值
            try:
                self.driver.execute_script(f"document.querySelector('input[type=\"text\"], input[type=\"email\"]').value = '{self.email}';")
                logger.info("👉 通过JavaScript设置邮箱")
                time.sleep(2)
            except:
                raise Exception(f"❌ 无法输入邮箱: {e}")
        
        # 等待密码输入框出现并输入密码
        try:
            logger.info("🔍 查找密码输入框...")

            password_input = self.wait_for_element_clickable(
                By.CSS_SELECTOR, "input[type='password']", 10
            )
            
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("✅ 密码输入完成")
            time.sleep(1)
            
        except TimeoutException:
            raise Exception("❌ 找不到密码输入框")
        
        # 点击登录按钮
        try:
            logger.info("🔍 查找登录按钮...")
            login_btn_selectors = [
                "//button[contains(text(), '登录')]",
                "//button[contains(text(), 'Login')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "button[type='submit']"
            ]
            
            login_btn = None
            for selector in login_btn_selectors:
                try:
                    if selector.startswith("//"):
                        login_btn = self.wait_for_element_clickable(By.XPATH, selector, 5)
                    else:
                        login_btn = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                    logger.info(f"✅ 找到登录按钮")
                    break
                except:
                    continue
            
            if not login_btn:
                raise Exception("❌ 找不到登录按钮")
            
            login_btn.click()
            logger.info("✅ 已点击登录按钮")
            
        except Exception as e:
            raise Exception(f"❌ 点击登录按钮失败: {e}")
        
        # 等待登录完成
        try:
            WebDriverWait(self.driver, self.WAIT_TIME_AFTER_LOGIN).until(
                lambda driver: "dashboard" in driver.current_url or "workspaces" in driver.current_url or "login" not in driver.current_url
            )
            
            # 检查当前URL确认登录成功
            current_url = self.driver.current_url
            if "dashboard" in current_url or "workspaces" in current_url or "login" not in current_url:
                logger.info(f"✅ 登录成功，当前URL: {current_url}")
                return True
            else:
                raise Exception("⚠️ 登录后未跳转到正确页面")
                
        except TimeoutException:
            # 检查是否登录失败
            try:
                error_selectors = [".error", ".alert-danger", "[class*='error']", "[class*='danger']"]
                for selector in error_selectors:
                    try:
                        error_msg = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if error_msg.is_displayed():
                            raise Exception(f"❌ 登录失败: {error_msg.text}")
                    except:
                        continue
                raise Exception("⚠️ 登录超时，无法确认登录状态")
            except Exception as e:
                raise e

    def get_balance(self):
        """获取当前账号的总余额"""
        try:
            logger.info("💰 获取账号余额...")
            
            # 跳转到仪表板页面
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            
            # 等待页面加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 尝试多种选择器查找余额元素
            balance_selectors = [
                "//*[contains(text(), '¥') or contains(text(), '￥') or contains(text(), '元')]",
                "//*[contains(@class, 'balance')]",
                "//*[contains(@class, 'money')]",
                "//*[contains(@class, 'amount')]",
                "//button[contains(@class, 'dollar')]",
                "//span[contains(@class, 'font-medium')]"
            ]
            
            for selector in balance_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        text = element.text.strip()
                        # 查找包含数字和货币符号的文本
                        if any(char.isdigit() for char in text) and ('¥' in text or '￥' in text or '元' in text):
                            # 提取数字部分
                            import re
                            numbers = re.findall(r'\d+\.?\d*', text)
                            if numbers:
                                balance = numbers[0]
                                logger.info(f"💰 找到余额: {balance}元")
                                return f"{balance}元"
                except:
                    continue
            
            logger.warning("未找到余额信息")
            return "未知"
            
        except Exception as e:
            logger.warning(f"获取余额时出错: {e}")
            return "未知"
    
    def wait_for_checkin_page_loaded(self, max_retries=None, wait_time=None):
        """等待签到页面完全加载，支持重试"""
        
        # 使用类常量作为默认值
        max_retries = max_retries if max_retries is not None else self.RETRY_COUNT_PAGE_LOAD
        wait_time = wait_time if wait_time is not None else self.RETRY_WAIT_TIME_PAGE_LOAD
        
        for attempt in range(max_retries):
            logger.info(f"⏳ 等待签到页面加载，尝试 {attempt + 1}/{max_retries}，等待 {wait_time} 秒...")
            time.sleep(wait_time)
            
            try:
                # 检查页面是否包含签到相关元素
                checkin_indicators = [
                    "button.checkin-btn",  # 优先使用这个选择器
                    "//button[contains(text(), '立即签到')]",
                    "//*[contains(text(), '每日签到')]",
                    "//*[contains(text(), '签到')]"
                ]
                
                for indicator in checkin_indicators:
                    try:
                        if indicator.startswith("//"):
                            element = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, indicator))
                            )
                        else:
                            element = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
                            )
                        
                        if element.is_displayed():
                            logger.info(f"✅ 找到签到页面元素")
                            return True
                    except:
                        continue
                
                logger.warning(f"⏳ 第 {attempt + 1} 次尝试未找到签到按钮，继续等待...")
                
            except Exception as e:
                logger.warning(f"❌ 第 {attempt + 1} 次检查签到页面时出错: {e}")
        
        return False
    
    def find_and_click_checkin_button(self):
        """查找并点击签到按钮 - 使用和单账号成功时相同的逻辑"""
        logger.info("🔍 查找立即签到按钮...")
        
        try:
            time.sleep(5)
            checkin_btn = self.wait_for_element_present(By.CSS_SELECTOR, "button.checkin-btn", 10)

            # 判断是否已经签到
            if not checkin_btn.is_enabled() and ("已签到" in checkin_btn.text or "disabled" in checkin_btn.get_attribute("class")):
                logger.info("👉 签到按钮显示为 '已签到' 且不可点击。")
                return "ALREADY_CHECKED_IN" # 返回已签到标记

            # 尝试点击签到按钮
            if checkin_btn.is_displayed() and checkin_btn.is_enabled():
                logger.info("👉 找到并点击 '立即签到' 按钮")
                checkin_btn.click()
                return "CLICK_SUCCESS" # 返回成功点击标记

            logger.error("⚠️ 找不到可点击的签到按钮")
            return "NO_BUTTON_FOUND" # 返回不可点击标记

        except TimeoutException:
            logger.error("⚠️ 在规定时间内找不到签到按钮")
            return "NO_BUTTON_FOUND" # 返回未找到签到按钮标记
        except Exception as e:
            logger.error(f"❌ 点击签到按钮时出错: {e}")
            return "ERROR"  # 返回错误标记
              
    def checkin(self):
        """执行签到流程"""
        logger.info("👉 跳转到签到页面...")
        self.driver.get(self.CHECKIN_URL)
        
        # 等待签到页面加载（最多重试3次，每次等待20秒）
        if not self.wait_for_checkin_page_loaded():
            raise Exception("❌ 签到页面加载失败，无法找到相关元素")
        
        # 查找并点击立即签到按钮
        click_result = self.find_and_click_checkin_button()
        
        if click_result == "ALREADY_CHECKED_IN":
            return "今日已签到"
        if click_result != "CLICK_SUCCESS":
            raise Exception("⚠️ 找不到立即签到按钮或按钮不可点击")
        
        logger.info("👉 已点击立即签到按钮")
        time.sleep(self.WAIT_TIME_AFTER_CHECKIN_CLICK)
        
        # 获取签到结果
        result_message = self.get_checkin_result()
        return result_message
    
    def get_checkin_result(self):
        """获取签到结果消息"""
        try:
            time.sleep(3)
            
            # 尝试查找各种可能的成功消息元素
            success_selectors = [
                ".alert-success",
                ".success",
                ".message",
                "[class*='success']",
                "[class*='message']",
                ".modal-content",  # 弹窗内容
                ".ant-message",    # Ant Design 消息
                ".el-message",     # Element UI 消息
                ".toast",          # Toast消息
                ".notification"    # 通知
            ]
            
            for selector in success_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        text = element.text.strip()
                        if text:
                            return text
                except:
                    continue
            
            # 如果没有找到特定元素，检查页面文本
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            important_keywords = ["成功", "签到", "获得", "恭喜", "谢谢", "感谢", "完成", "已签到", "连续签到"]
            
            for keyword in important_keywords:
                if keyword in page_text:
                    # 提取包含关键词的行
                    lines = page_text.split('\n')
                    for line in lines:
                        if keyword in line and len(line.strip()) < 100:  # 避免提取过长的文本
                            return line.strip()
            
            return "⚠️ 签到完成，但未找到具体结果消息"
            
        except Exception as e:
            return f"❌ 获取签到结果时出错: {str(e)}"
    
    def run(self):
        """单个账号执行流程"""
        try:
            logger.info(f"⏳ 开始处理账号")
            
            # 登录
            if self.login():
                # 签到
                result = self.checkin()
                logger.info(f"📋 签到结果: {result}")
                # 获取余额
                balance = self.get_balance()
                logger.info(f"📋 签到结果: {result}, 💰 余额: {balance}")
                return True, result, balance
            else:
                raise Exception("❌ 登录失败")
                
        except Exception as e:
            error_msg = f"❌ 自动签到失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知"
        
        finally:
            if self.driver:
                self.driver.quit()

class MultiAccountManager:
    """多账号管理器 - 简化配置版本"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TG_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TG_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        accounts = []
        logger.info("⏳ 开始加载账号配置...")
        
        # 方法1: 统一从 LEAFLOW_ACCOUNTS 读取多账号（支持逗号或换行）
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            try:
                logger.info("⏳ 尝试解析多账号，支持逗号或换行分隔")
                account_pairs = [
                    pair.strip() for pair in accounts_str.replace('\r', '').replace(',', '\n').split('\n') if pair.strip()
                ]
                logger.info(f"👉 共找到 {len(account_pairs)} 个账号")
                
                for i, pair in enumerate(account_pairs):
                    if ':' in pair:
                        email, password = pair.split(':', 1)
                        email = email.strip()
                        password = password.strip()
                        
                        if email and password:
                            accounts.append({
                                'email': email,
                                'password': password
                            })
                            logger.info(f"✅ 成功添加第 {i+1} 个账号")
                        else:
                            logger.warning(f"❌ 账号对格式错误")
                    else:
                        logger.warning(f"❌ 账号对缺少冒号分隔符")
                
                if accounts:
                    logger.info(f"👉 从冒号分隔格式成功加载了 {len(accounts)} 个账号")
                    return accounts
                else:
                    logger.warning("⚠️ 冒号分隔配置中没有找到有效的账号信息")
            except Exception as e:
                logger.error(f"❌ 解析冒号分隔账号配置失败: {e}")
        
        # 方法2: 单账号格式
        single_email = os.getenv('LEAFLOW_EMAIL', '').strip()
        single_password = os.getenv('LEAFLOW_PASSWORD', '').strip()
        
        if single_email and single_password:
            accounts.append({
                'email': single_email,
                'password': single_password
            })
            logger.info("👉 加载了单个账号配置")
            return accounts
        
        # 如果所有方法都失败
        logger.error("⚠️ 未找到有效的账号配置")
        logger.error("⚠️ 请检查以下环境变量设置:")
        logger.error("⚠️ 1. 多账号变量: LEAFLOW_ACCOUNTS 支持以下两种格式：")
        logger.error("   - 逗号分隔: user1@gmail.com:pass1,user2@qq.com:pass2")
        logger.error("   - 换行分隔: user1@gmail.com:pass1\n user2@qq.com:pass2")
        logger.error("⚠️ 2. 单账号变量 LEAFLOW_EMAIL 和 LEAFLOW_PASSWORD")
        
        raise ValueError("⚠️ 未找到有效的账号配置")
    
    def send_notification(self, results):
        """发送汇总通知到Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("⚠️ Telegram配置未设置，跳过通知")
            return
        
        try:
            SUCCESS_MSG = "今日已签到"
            script_success_count = sum(1 for _, success, result, _ in results if success and result != SUCCESS_MSG)  # 脚本签到的账号数量
            already_checked_count = sum(1 for _, _, result, _ in results if result == SUCCESS_MSG)  # 手动签到的账号数量
            failure_count = sum(1 for _, success, _, _ in results if not success)  # 签到失败的账号数量
            total_success_count = already_checked_count + script_success_count  # 签到成功的账号数量 (含已手动签到)
            total_count = len(results)  # 账号总数量

            message = f"🎁 <strong>Leaflow自动签到通知</strong>\n"
            message += f"=========================\n"
            message += f"📋 共处理账号: {total_count} 个，其中：\n"
            message += f"👏 手动签到: {already_checked_count} 个\n"
            message += f"🚀 脚本签到: {script_success_count} 个\n"
            message += f"✅ 签到成功: {total_success_count} 个\n"
            message += f"❌ 签到失败: {failure_count} 个\n"
            message += f"=========================\n"
         
            for index, (email, success, result, balance) in enumerate(results):
                if success and result != SUCCESS_MSG:
                    status = "✅" # 脚本签到
                elif result == SUCCESS_MSG:
                    status = "⏳" # 手动签到
                else:
                    status = "❌" # 失败
                
                # 签到详情消息
                message += f"<strong>账号:</strong> <code>{email}</code>\n"
                message += f"{status} {result}\n💰 当前余额：{balance}\n"
                if index < total_count - 1:
                    message += f"-------------------------------\n"
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Telegram 通知发送成功")
            else:
                logger.error(f"❌ Telegram 通知发送失败: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Telegram 通知发送出错: {e}")
    
    def run_all(self):
        """运行所有账号的签到流程"""
        logger.info(f"👉 开始执行 {len(self.accounts)} 个账号的签到任务")
        
        results = []
        
        for i, account in enumerate(self.accounts, 1):
            logger.info(f"👉 处理第 {i}/{len(self.accounts)} 个账号")
            
            try:
                auto_checkin = LeaflowAutoCheckin(account['email'], account['password'])
                success, result, balance = auto_checkin.run()
                results.append((account['email'], success, result, balance))
                
                # 在账号之间添加间隔，避免请求过于频繁
                if i < len(self.accounts):
                    wait_time = 5
                    logger.info(f"⏳ 等待{wait_time}秒后处理下一个账号...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                error_msg = f"❌ 处理账号时发生异常: {str(e)}"
                logger.error(error_msg)
                results.append((account['email'], False, error_msg, "未知"))
        
        # 发送汇总通知
        self.send_notification(results)
        
        # 返回总体结果
        success_count = sum(1 for _, success, _, _ in results if success)
        return success_count == len(self.accounts), results

def main():
    """主函数"""
    try:
        manager = MultiAccountManager()
        overall_success, detailed_results = manager.run_all()
        success_count = sum(1 for _, success, _, _ in detailed_results if success)
        
        if overall_success:
            logger.info("✅ 所有账号签到成功")
            exit(0)
        else:
            logger.warning(f"⚠️ 部分账号签到失败: {success_count}/{len(detailed_results)} 成功")
            exit(0)
            
    except Exception as e:
        logger.error(f"❌ 脚本执行出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
