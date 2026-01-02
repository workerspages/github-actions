
# GitHub Actions - 私有化定时任务管理面板

这是一个轻量级、私有化的定时任务管理面板，模仿 GitHub Actions 的体验。支持 Python 和 Node.js 脚本，内置 Playwright 环境，适合运行各类自动化签到、爬虫及定时维护脚本。

![Dashboard Screenshot](https://via.placeholder.com/800x400?text=Dashboard+Preview)

## ✨ 功能特性

- **多语言运行时**：支持 Python 3 (含 venv 隔离) 和 Node.js 20。
- **全能环境**：内置 Chromium 内核和 Playwright，轻松处理浏览器自动化任务。
- **Web 可视化**：基于 Vue 3 + Naive UI 的现代化管理界面，支持在线编辑代码。
- **Crontab 调度**：支持标准的 Cron 表达式，精确控制任务运行时间。
- **日志实时查看**：支持任务运行日志的实时查看与持久化存储。
- **Secrets 管理**：支持环境变量（Secrets）管理，敏感信息不硬编码。
- **New! 外部数据库支持**：支持 SQLite（默认）及 MariaDB/MySQL 外部数据库连接。

## 🚀 快速部署 (Docker Compose)

### 1. 创建目录与文件
创建一个目录（例如 `my-actions`），并在其中创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  github-actions:
    image: ghcr.io/workerspages/github-actions:github-actions-mariadb
    container_name: github-actions
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data        # 数据库(SQLite)及虚拟环境存储
      - ./scripts:/app/scripts  # 脚本文件存储
    environment:
      - TZ=Asia/Shanghai
      # 管理员账号设置
      - ADMIN_USER=admin
      - ADMIN_PASSWORD=admin
      # JWT 密钥 (建议修改为随机字符串)
      - JWT_SECRET=your_secret_key_change_me
      
      # === 数据库配置 (可选) ===
      # 默认使用内置 SQLite，无需配置
      # - DATABASE_URL=sqlite:////app/data/github-actions.db
      
      # 如需连接外部 MariaDB/MySQL，请取消下方注释并修改参数：
      # - DATABASE_URL=mysql+pymysql://root:password@192.168.1.100:3306/github_actions
```

### 2. 启动服务
```bash
docker-compose up -d
```

### 3. 访问面板
浏览器访问 `http://你的IP:8000`，默认账号密码均为 `admin`（或你在 yaml 中配置的值）。

## ⚙️ 配置说明

### 环境变量 (Environment Variables)

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `ADMIN_USER` | `admin` | 面板登录用户名 |
| `ADMIN_PASSWORD` | `admin` | 面板登录密码 |
| `JWT_SECRET` | 随机生成 | 用于 Token 加密，**生产环境务必修改固定**，否则重启后需重新登录 |
| `DATABASE_URL` | `sqlite:////app/data/github-actions.db` | 数据库连接字符串 |
| `TZ` | `Asia/Shanghai` | 容器时区 |

### 数据库连接详解 (Database Support)

本项目基于 SQLAlchemy，支持多种数据库后端。

#### 1. SQLite (默认)
无需任何配置，数据文件存储在 `/app/data/github-actions.db`。适合单机、轻量级使用。

#### 2. MariaDB / MySQL (推荐生产环境)
如果你希望数据存储在外部数据库，或者需要更高的并发性能，可以使用 MariaDB 或 MySQL。
在 `docker-compose.yml` 中添加以下环境变量：

```bash
DATABASE_URL=mysql+pymysql://<用户名>:<密码>@<主机地址>:<端口>/<数据库名>
```

**示例：**
```bash
DATABASE_URL=mysql+pymysql://root:123456@192.168.1.10:3306/my_task_db
```
> **注意**：使用外部数据库前，请确保对应的数据库（如 `my_task_db`）已在 MySQL 中创建。表结构会自动初始化。

## 📝 脚本编写指南

### Python 模式 (默认)
直接编写 Python 代码即可。依赖包请在编辑页面的 **"依赖"** 标签页中填写 `requirements.txt` 内容。

```python
import os
from loguru import logger

# 获取 Secrets
token = os.getenv("MY_TOKEN")
logger.info("任务开始运行...")
```

### Node.js 模式
在代码的第一行添加魔法注释 `// runtime: node`，系统会自动切换为 Node.js 运行时。

```javascript
// runtime: node
const axios = require('axios');

console.log("Node.js 任务开始...");
```

## 📂 项目结构

```text
.
├── backend/            # FastAPI 后端源码
├── frontend/           # Vue3 + NaiveUI 前端源码
├── checkin/            # 内置示例脚本 (签到脚本等)
├── data/               # (自动生成) 数据存储目录
├── scripts/            # (自动生成) 脚本文件存储目录
├── Dockerfile          # 构建文件
└── docker-compose.yml  # 部署文件
```

## 🛠️ 本地开发

1. **后端**：
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
2. **前端**：
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## 📄 License
MIT
