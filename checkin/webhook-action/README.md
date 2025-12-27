# 方法一：uptime webhook 通知 —— CF Worker 启动

> **优势：不依赖 github action，没有 action 排队问题，保活更及时**

## 部署 webhook 通知 API

- 代码：`sap-webhook-cf.js`
- 环境变量
  - EMAIL=sap登录邮箱，必须
  - PASSWORD=sap登录密码，必须
  - APP_URLS=SAP应用的URL地址，多个地址可每行填写1个，必须
  - CHAT_ID=TG机器人或频道ID，可选
  - BOT_TOKEN=TG机器人Token，可选

## uptime kuma 通知设置

- **显示名称**：填一个易于分辨的名称，如 `SAP离线`
- **通知类型**: `Webhook`
- **Post URL**: `https://上面部署的worker地址/webhook/restart?appUrl=[URL]`
- **请求体**: 选择 `预设 - application/json` (然后不要在下方出现的任何文本框中填写内容)
- **额外 Header**: 保持 `禁用` 状态
- **保存**

**注意**：将 `[URL]` 替换为 sap 应用的 https 地址

---

# 方法二：uptime webhook 通知 —— github action 启动

## 部署 worker api

- 代码：`uptime-webhook.js`
- 环境变量：
  - `GITHUB_TOKEN` = <您的GitHub Personal Access Token>，该令牌需要有触发 GitHub Actions 的权限
  - `SECRET_TOKEN` = <设置的密码>，用于验证请求来源，以保护API端点的安全

- 部署此脚本后，将 Uptime Kuma 的 Webhook URL 设置为：

```
https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>
```

## 修改目标仓库 action 的触发方式

```yml
name: your action

on:
  workflow_dispatch:
  # schedule:
  #   - cron: '0 */2 * * *'

  # 当 Uptime Kuma API 发送 'service-down-alert' 事件时触发此工作流。
  repository_dispatch:
    types: [service-down-alert]

jobs:
  deploy-and-sync:
    runs-on: ubuntu-latest
    ..............

    steps:
      - name: Check Trigger Event
        run: |
          echo "Workflow triggered by: ${{ github.event_name }}"
          if [[ "${{ github.event_name }}" == "repository_dispatch" ]]; then
            echo "触发事件类型 (Event Type): ${{ github.event.action }}"
            echo "收到来自 Uptime Kuma 的下线通知，开始执行自动恢复部署流程..."
          elif [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "工作流被手动触发，开始执行部署..."
          else
            echo "工作流由计划任务触发，开始执行部署..."
          fi
    ..............
```

## 手动测试

在终端中运行以下代码：

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{ "heartbeat": { "status": 0, "msg": "来自curl的手动测试", "time": "2025-09-16T00:00:00Z" }, "monitor": { "name": "手动验证监控" }, "msg": "这是一条手动验证通知。" }' \
  'https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>'
```

## uptime 设置

### 在uptime通知中设置webhook

- **显示名称**：填一个易于分辨的名称，如 `SAP离线`
- **通知类型**: `Webhook`
- **Post URL**: 上述两种方法二选一 (请确保此URL完整且正确)
- **请求体**: 选择 `预设 - application/json` (然后不要在下方出现的任何文本框中填写内容)
- **额外 Header**: 保持 `禁用` 状态
- **保存**

### 修改监控项

- **监控项类型**：选择 `HTTP(s) - 关键字`
- **URL**: 填写监控的网站，如 `https://webapp.ap21.hana.ondemand.com`
- **关键字**: 填写一个在网站上必然出现的词，例如 `Hello`（注意大小写）
- **心跳间隔**: 建议 `600` 秒，即10分钟
- **通知**：关联刚刚设置的 `SAP离线` 通知
- **其他默认，点击保存**
