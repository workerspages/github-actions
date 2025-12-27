

# GitHub Actions - 私有化定时任务调度平台

<div align="center">

![Docker Image Size](https://img.shields.io/docker/image-size/ghcr.io/yourusername/github-actions?color=blue&label=Docker%20Image)
![Python](https://img.shields.io/badge/Backend-FastAPI-green)
![Vue](https://img.shields.io/badge/Frontend-Vue3%20%2B%20NaiveUI-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

**一个完全复刻 GitHub Actions 体验的私有化定时任务平台。**
**专为解决公共 CI/CD 服务 IP 被封锁、签到脚本无法运行而生。**

</div>

---

## 📖 项目介绍

**GitHub Actions** 是一个基于 Docker 部署的轻量级任务调度系统。它允许你在自己的服务器上运行 Python 脚本，完美解决了使用 GitHub Actions 等公共服务进行网站签到、爬虫任务时面临的 **IP 封锁** 问题。

不仅如此，GitHub Actions 还引入了 **“随机延时”** 机制，模拟真人操作时间，极大地提高了账号的安全性。

### ✨ 核心特性

*   **🛡️ 私有化部署**：运行在自己的 VPS 或 NAS 上，拥有独立的 IP 地址，告别“万人骑”IP。
*   **🎭 智能反爬虫**：支持 **Random Delay (随机延时)** 设置。例如设置 300秒，任务会在 Cron 触发后的 0-300秒内随机时间执行。
*   **💻 沉浸式编辑器**：集成 **Monaco Editor** (VS Code 同款核心)，支持 Python 语法高亮、代码补全。
*   **📦 依赖自动管理**：支持为每个脚本单独配置 `requirements.txt`，系统会自动创建虚拟环境 (venv) 并安装依赖。
*   **🌐 Selenium 支持**：内置 Chrome 浏览器和驱动，完美支持自动化操作（需开启 Headless 模式）。
*   **📝 实时结构化日志**：完全复刻 GitHub Actions 的日志体验，分步骤展示（环境准备 -> 依赖安装 -> 脚本执行），支持实时刷新。
*   **🔐 Secrets 管理**：环境变量加密存储，脚本中通过 `os.environ` 直接调用，保护你的 Cookie 和 Token。
*   **🎨 现代化 UI**：基于 Vue 3 + Naive UI 的暗黑模式界面，大气、时尚、流畅。

---

## 🚀 快速开始 (部署指南)

推荐使用 Docker Compose 进行一键部署，支持 x86_64 和 arm64 架构。

### 1. 安装 Docker
如果您还没有安装 Docker，请先安装：
```bash
curl -fsSL https://get.docker.com | bash
```

### 2. 创建部署文件
在服务器上创建一个目录（例如 `github-actions`），并创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  github-actions:
    image: yesyunxin/github-actions:latest
    container_name: github-actions
    restart: unless-stopped
    ports:
      - "8000:8000"             # 外部访问端口:容器内部端口
    volumes:
      - ./data:/app/data        # 数据库持久化
      - ./scripts:/app/scripts  # 脚本文件持久化
    environment:
      - TZ=Asia/Shanghai

      # 自定义管理员密码 (建议修改)
      - ADMIN_USER=admin
      - ADMIN_PASSWORD=admin

      # JWT 加密密钥 (生产环境请务必修改为长随机字符串)
      - JWT_SECRET=change_this_to_a_secure_random_string
```

### 3. 启动服务
在包含 `docker-compose.yml` 的目录下执行：

```bash
docker-compose up -d
```

### 4. 访问系统
*   **地址**: `http://你的服务器IP:8080`
*   **默认账号**: `admin`
*   **默认密码**: `admin` (或你在 yaml 中设置的密码)

---

## 📖 使用指南

### 1. 编写脚本
点击右上角 **“新建任务”**。
*   **Python 代码**: 你的逻辑代码。
*   **依赖 (Requirements)**: 如果脚本需要 `requests` 或 `selenium`，请在右侧标签页填写，每行一个。

### 2. 使用 Secrets (环境变量)
在左侧菜单点击 **“Secrets 管理”** 添加变量，例如 `JD_COOKIE`。
在 Python 脚本中这样使用：
```python
import os
cookie = os.environ.get("JD_COOKIE")
print(f"当前 Cookie: {cookie}")
```
> **提示**: 系统默认内置了 `GITHUB_ACTIONS=true` 变量，方便直接迁移 GitHub 的脚本。
> 
> **如果出错**：删除脚本Python 代码 中的 `if os.getenv('GITHUB_ACTIONS'):`

### 3. Selenium 脚本示例
GitHub Actions 完美支持 Selenium。在脚本中使用时，**必须**添加以下 Docker 兼容参数：

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def run_browser():
    chrome_options = Options()
    # --- Docker 环境必须添加以下参数 ---
    chrome_options.add_argument('--headless')           # 无头模式
    chrome_options.add_argument('--no-sandbox')         # 禁用沙盒
    chrome_options.add_argument('--disable-dev-shm-usage') # 解决内存崩溃问题
    chrome_options.add_argument('--disable-gpu')
    # ------------------------------------
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://www.google.com")
    print(driver.title)
    driver.quit()

if __name__ == "__main__":
    run_browser()
```

### 4. 查看日志
点击任务卡片上的 **“日志”** 按钮，侧边栏会弹出执行详情。
*   ✅ **Set up job**: 环境初始化
*   ✅ **Install dependencies**: 依赖安装日志
*   ✅ **Run script**: 你的脚本输出 (print 内容)

---

## 🛠️ 二次开发 (Developer)

如果你想自己修改源码并构建。

### 项目结构
```text
GitHubActions/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 核心逻辑 (API, 调度, 数据库, 日志)
│   │   └── ...
│   └── requirements.txt
├── frontend/               # Vue3 前端
│   ├── src/
│   │   ├── views/          # 页面 (Dashboard, Secrets)
│   │   └── components/     # 组件 (Editor)
│   └── ...
├── Dockerfile              # 多阶段构建文件
└── docker-compose.yml
```

### 本地运行

**后端:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端:**
```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173 (需配置 vite.config.js 代理到后端)
```

---

## ❓ 常见问题 (FAQ)

**Q: 为什么 Selenium 报错 `Chrome instance exited`?**
A: 这是因为 Docker 共享内存不足。请务必在 Python 脚本的 Chrome Options 中添加 `--disable-dev-shm-usage` 参数。详情请参考上文“Selenium 脚本示例”。

**Q: 依赖安装太慢怎么办？**
A: 系统默认已配置使用 **阿里云 PyPI 镜像源** 加速依赖安装，通常速度很快。

**Q: 如何迁移数据？**
A: 所有数据存储在映射的 `./data/github-actions.db` (SQLite) 文件中。备份或迁移该文件即可。

---

### 🛠️ 必须要做的修改 (Python 脚本)

在 GitHub Actions 中，有时即便不加某些参数也能跑，但在 Docker 容器内，**必须**加上以下参数，否则 Chrome 进程会崩溃：

在你的脚本 `setup_driver` 部分，确保有这三行：

```python
def setup_driver(self):
        chrome_options = Options()
        
        # =========== Docker 环境必须添加的参数 (开始) ===========
        # 1. 解决内存不足导致 Chrome 崩溃的关键参数
        chrome_options.add_argument('--disable-dev-shm-usage') 
        
        # 2. Docker 中以 Root 运行必须禁用沙盒
        chrome_options.add_argument('--no-sandbox')
        
        # 3. 无头模式 (因为 Docker 没有显示器)
        chrome_options.add_argument('--headless')
        
        # 4. 禁用 GPU (Docker 通常没有 GPU)
        chrome_options.add_argument('--disable-gpu')
        # =========== Docker 环境必须添加的参数 (结束) ===========

        # 其他常规配置
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 初始化驱动
        self.driver = webdriver.Chrome(options=chrome_options)
```

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源。欢迎 Star 和 Fork！
