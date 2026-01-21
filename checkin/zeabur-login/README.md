# Zeabur Keep Alive

通过 GitHub Actions 定时登录 Zeabur 控制台，保持账户活跃。支持 Telegram 通知和自动更新 Cookie。

## 功能

- ✅ 支持 Cookie 登录（优先）
- ✅ 支持 Magic Link 登录（Cookie 失效时使用）
- 📸 登录成功后截图并发送到 Telegram
- 🔄 自动更新 Cookie 到 GitHub Secrets

## 配置步骤

### 1. 首次设置（Magic Link）

1. 访问 [Zeabur 登录页](https://zeabur.com/login)
2. 输入邮箱，点击「发送登录链接」
3. 打开邮箱，**复制完整的登录链接**（不要点击）
4. 链接格式：`https://zeabur.com/api/magic-link/callback?code=xxx&state=xxx`
5. 将链接设置到 `ZEABUR_MAGIC_LINK` Secret

> 首次 Magic Link 登录成功后，Cookie 会自动保存，后续无需再设置 Magic Link。

### 2. 创建 Telegram Bot

1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 创建 Bot
3. 保存 Bot Token
4. 获取 Chat ID：
   - 给 Bot 发送任意消息
   - 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - 找到 `chat.id` 字段

### 3. 创建 GitHub Personal Access Token

1. [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. 生成 Token，勾选 **repo** scope

### 4. 配置 GitHub Secrets

进入仓库 **Settings → Secrets and variables → Actions**：

| Secret 名称 | 说明 |
|------------|------|
| `ZEABUR_MAGIC_LINK` | Magic Link（首次使用或 Cookie 失效时设置） |
| `ZEABUR_COOKIE` | Cookie（自动生成，无需手动设置） |
| `REPO_TOKEN` | GitHub PAT（用于自动更新 Cookie） |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_CHAT_ID` | Telegram Chat ID |

## 登录优先级

```
Cookie（优先）→ Magic Link（备选）
```

- 日常运行：自动使用 Cookie
- Cookie 过期：尝试 Magic Link，成功后自动更新 Cookie
- 两者都失败：发送 Telegram 通知，提示设置新的 Magic Link

## 执行频率

默认每天 08:00（北京时间）执行。修改 `.github/workflows/keep-alive.yml` 中的 cron：

```yaml
schedule:
  - cron: '0 0 * * *'     # 每天
  - cron: '0 */12 * * *'  # 每12小时
```

## 手动测试

```bash
pip install -r requirements.txt
playwright install chromium
export ZEABUR_COOKIE="your_cookie"  # 或 ZEABUR_MAGIC_LINK
export TG_BOT_TOKEN="your_bot_token"
export TG_CHAT_ID="your_chat_id"
python scripts/keep_alive.py
```
