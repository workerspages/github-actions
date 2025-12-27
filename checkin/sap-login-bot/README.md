# SAP BTP Auto Login Bot

这个项目用于 **自动登录 SAP BTP 试用账号**，并通过 **GitHub Actions + Playwright**  
每隔 10 天执行一次，完成以下任务：

1. 自动登录 SAP BTP 试用账号（邮箱 + 密码两步验证）。  
2. 点击 **“转到您的试用账户”**，进入试用账户主页。  
3. 截取两张截图：  
   - 登录成功后的页面  
   - 进入试用账户后的页面  
4. 自动将截图推送到 **Telegram**。  
5. 登录失败或操作失败时，会截取错误页面截图并推送到 Telegram。  
6. **自动上传截图到 GitHub Artifact**，方便保存和下载历史记录。  

---


## 🚀 部署步骤

### 1. Fork 项目
点击右上角 **Fork**，把本项目复制到你自己的 GitHub 仓库。

---

### 2. 配置 GitHub Secrets
在你的仓库里，依次进入：
Settings → Secrets and variables → Actions → New repository secret

添加以下 3 个 Secrets：

| 名称 | 说明 |
|------|------|
| `SAP_ACCOUNTS` | SAP BTP 登录账号和密码 复制SAP_ACCOUNTS.json的内容替换成自己的|
| `TG_BOT_TOKEN` | Telegram 机器人 Token（从 @BotFather 获取） |
| `TTG_CHAT_ID` | Telegram Chat ID（可通过 @userinfobot 查询） |

---
登陆账号采用json格式： <br> 
[
  {"email": "user1@example.com", "password": "password1"},
  {"email": "user2@example.com", "password": "password2"}
] 

### 3. 启用 GitHub Actions
进入仓库的 **Actions** 页面，启用 workflow。  
系统会自动按照 `login.yml` 定时运行脚本。

---

### 4. 手动触发（可选）
如果不想等 10 天，可以手动执行一次：
Actions → SAP BTP Auto Login → Run workflow
---

## 🖼️ 运行效果

运行成功后，Telegram 会收到两张截图：

1. **登录成功页面**
✅ SAP BTP 登录成功页面
2. **试用账户主页**
✅ 已进入 SAP BTP 试用账户页面

失败时，会收到：
❌ SAP BTP 操作失败截图
并附带错误页面截图。

---

## 📦 GitHub Artifact

每次 workflow 运行完成后，截图会自动上传到 **Artifact**，文件包括：

- `login-success.png` → 登录成功截图  
- `trial-account.png` → 试用账户页面截图  
- `error.png` → 登录或操作失败截图（如果存在）  

下载方式：  
Actions → 选择对应运行记录 → Artifacts → sap-btp-screenshots

📌 注意事项

脚本使用 Playwright 自动化浏览器操作。

首次运行时会自动安装 Chromium 浏览器。

如果 SAP 登录页面的元素发生变化（选择器不同），需要在 scripts/login.js 中调整 SELECTORS。

Consent Banner/Cookie 弹窗会自动关闭，避免阻挡按钮点击。
