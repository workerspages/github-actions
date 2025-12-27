# Leaflow 自动签到脚本

![Python](https://img.shields.io/badge/Python-3.7%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

* TG交流反馈群组：https://t.me/eooceu
* youtube视频教程：https://www.youtube.com/@eooce


Leaflow 多账号自动签到脚本，支持 Telegram 通知和 GitHub Actions 自动化运行。

## 功能特性

- ✅ 支持多个 Leaflow 账号自动签到
- 🤖 基于 Selenium 实现自动化操作
- 📱 自动处理网站弹窗和验证码
- 📢 支持 Telegram 通知推送
- ⏰ 支持 GitHub Actions 定时自动执行
- 🔄 智能重试机制，提高签到成功率
- 📊 详细的日志记录和错误处理

## 使用方法

#### 配置账号信息

脚本支持两种种方式配置账号信息：

##### 方式一：单个账号
```bash
LEAFLOW_EMAIL    your_email@example.com
LEAFLOW_PASSWORD    your_password
```

##### 方式二：多个账号（分隔符方式，向后兼容）
```bash
LEAFLOW_ACCOUNTS

email1@example.com:password1,email2@example.com:password2
```


### GitHub Actions 自动运行

1. Fork 本仓库
2. 在仓库 Settings > Secrets and variables > Actions 中添加以下 secrets：
   - `LEAFLOW_ACCOUNTS`: 账号信息(账号密码之间英文冒号分隔,多账号之间英文逗号分隔)

Telegram 通知配置
   - `TELEGRAM_BOT_TOKEN`（可选）: Telegram Bot Token
   - `TELEGRAM_CHAT_ID`（可选）: Telegram Chat ID

3. 启用 Actions 启用工作流

## 配置说明

| 环境变量 | 必需 | 说明 |
|---------|------|------|
| `LEAFLOW_EMAIL` | 否* | 单个账号邮箱（方式一） |
| `LEAFLOW_PASSWORD` | 否* | 单个账号密码（方式一） |
| `LEAFLOW_ACCOUNTS` | 否* | 多个账号密码，逗号分隔（方式二,推荐） |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 否 | Telegram Chat ID |

*注：以上账号配置方式至少需要配置一种


## 注意事项

- 请确保账号信息正确无误,并正确配置secrets
- 脚本会在账号间间隔 10 秒钟，避免请求过于频繁
- 在 GitHub Actions 中运行时，脚本会自动使用无头模式（headless mode）
- 请遵守网站的使用条款，合理使用自动化脚本

## 许可证
GPL 3.0

## 郑重声明
* 禁止新建项目将代码复制到自己仓库中用做商业行为，违者必究
* 用于商业行为的任何分支必须完整保留本项目说明，违者必究
* 请遵守当地法律法规,禁止滥用做公共代理行为





