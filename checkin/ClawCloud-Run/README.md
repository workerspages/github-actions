# ClawCloud-Run 自动登录助手

这是一个通过 GitHub Actions 实现的自动化脚本，用于定时自动登录 [ClawCloudRun](https://console.run.claw.cloud/signin?link=WRJQ4YKZNLI5)，以保持账户活跃。

## ✨ 主要功能

- **🤖 自动登录**: 定时执行登录操作，避免账户因不活跃而被清空项目。
- **🌍 区域自适应**: 自动检测并跳转到账户所在的区域。
- **🔒 安全验证支持**:
    - 支持设备授权验证 (Device Verification)。
    - 支持两步验证 (2FA)，包括：
        - GitHub 移动应用批准。
        - 通过 Telegram 机器人发送验证码 (`/code 123456`)。
- **🔔 实时通知**: 通过 Telegram 机器人发送登录结果、设备验证和两步验证请求。
- **🍪 Cookie 自动更新**: 登录成功后，可自动更新 GitHub Secrets 中的 `GH_SESSION`，免去手动更新的麻烦。

## 🚀 如何部署

1.  **Fork 本仓库**: 点击右上角的 "Fork" 按钮，将此项目复制到你自己的 GitHub 账户下。
2.  **配置 Secrets**: 在你 Fork 的仓库中，进入 `Settings` -> `Secrets and variables` -> `Actions`。点击 `New repository secret`，添加以下变量：

## ⚙️ 配置变量

| Secret 名称       | 是否必须       | 描述                                                                                                                              |
| ----------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `GH_USERNAME`     | **是**   | 你的 GitHub 用户名。                                                                                                                |
| `GH_PASSWORD`     | **是**   | 你的 GitHub 密码。                                                                                                                |
| `GH_SESSION`      | **是**       | GitHub 的 `user_session` Cookie 值。首次运行时可不填，脚本会自动获取并提示你更新。如果配置了 `REPO_TOKEN`，脚本可自动更新此值。 |
| `TG_BOT_TOKEN`    | **是**        | 用于发送通知的 Telegram Bot Token。如果你需要接收登录状态或进行两步验证，则必须配置。                                              |
| `TG_CHAT_ID`      | **是**        | 你的 Telegram User ID 或 Channel ID，用于接收机器人消息。                                                                        |
| `REPO_TOKEN`      | **是**       | GitHub Personal Access Token。如果希望脚本自动更新 `GH_SESSION`，需要提供此 Token。请授予 `repo` 权限。                            |
| `TWO_FACTOR_WAIT` | 否       | 两步验证的等待时间（秒），默认为 `120`。                                                                                              |


## ▶️ 如何运行

- **自动运行**: 默认配置下，脚本会**每 5 天**自动运行一次。你可以在 `.github/workflows/keep-alive.yml` 文件中修改 `cron`表达式来调整运行频率。
- **手动运行**:
    1.  进入 Fork 后的仓库页面。
    2.  点击 `Actions` 选项卡。
    3.  在左侧选择 `ClawCloud 自动登录保活`。
    4.  点击右侧的 `Run workflow` 按钮，即可立即触发一次登录任务。

## 🙏 致谢

本项目基于 [oyz8/ClawCloud-Run](https://github.com/oyz8/ClawCloud-Run) 做了些调整，感谢原作者的贡献。
