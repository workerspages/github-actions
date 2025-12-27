# Databricks Keep-Alive Workers

这个 Worker 脚本用于监控和自动重启 Databricks App，确保它们保持运行状态。

Databricks部署节点视频教程：https://youtu.be/r35kK77PlLg

## 说明

本项目由老王的 [原始项目](https://github.com/eooce/Databricks-keepalive-workers) 和`灰色轨迹`的 [修改项目](https://github.com/jy02739245/Databricks-keepalive-workers) 整合而来，UI界面改为**半透明爆玻璃**效果，支持**一键创建 APP**

## 部署指南

### 部署

1. 登录你的cloudflare，创建一个新的workers，名称随意，编辑代码，删除原示例代码
2. 打开此项目的_worker.js文件，复制代码粘贴到workers代码框中，部署
3. 设置cron触发器，推荐10分钟

### 配置变量

1. **DATABRICKS_HOST**: Databricks 工作区 Host，例如 `https://abc-123456789.cloud.databricks.com`
2. **DATABRICKS_TOKEN**: 用于 API 访问的个人访问令牌，点击右上角用户设置-选择"Developer" -> "Access Tokens"生成新的访问令牌
3. **ARGO_DOMAIN**：argo域名，若需保活则必须此变量
4. **(可选) TG_BOT_TOKEN**: 用于发送通知的 Telegram Bot 令牌
5. **(可选) TG_CHAT_ID**: 接收通知的聊天caht id

## 使用说明

部署完成后，你可以通过以下方式使用：

### Web 管理界面

访问 Worker 的根路径 `/` 可以打开 Web 管理界面，提供以下功能：

### API 端点

- `GET /` - 显示管理界面
- `GET /status` - 获取当前所有 Apps 的状态
- `GET /check` - 智能检查（ARGO优先）
- `GET /check-argo` - 检查 ARGO 域名状态
- `POST /start` - 手动启动所有停止的 Apps
- `POST /create-app` - 创建/替换 APP（先删除再创建新APP）
- `GET /config` - 查看当前配置信息
- `POST /test-notification` - 测试 Telegram 通知

## 故障排除

### Apps 未自动启动

1. 检查 DATABRICKS_HOST 和 DATABRICKS_TOKEN 是否正确配置
2. 确认 Token 具有足够权限
3. 检查 Worker 日志以获取更多信息

### Telegram 通知未发送

1. 确认 TG_BOT_TOKEN 和 TG_CHAT_ID 已正确配置
2. 验证 Bot 是否有向指定 Chat ID 发送消息的权限
3. 使用 `/test-notification` 端点测试通知功能

### 定时任务未执行

1. 检查 Cron Trigger 配置是否正确
2. 确认 Worker 已正确部署
3. 查看 Worker 日志确认定时任务是否被触发

## Uptime Kuma 配置

### 监控配置

- 监控类型：`HTTP(S)-关键字`
- 监控地址：`https://本项目worker地址/check-argo`
- 关键字: `"online": true`

### 通知保活

- 通知类型：`webhook`
- 显示名称：`databricks离线`
- POST URL：`https://本项目worker地址/start`
- 请求体：`预设-application/json`
