

# GitHub Actions - 全能型私有化定时任务平台

<div align="center">

![Docker Image Size](https://img.shields.io/badge/Image%20Size-~1.5GB-blue)
![Environment](https://img.shields.io/badge/Env-Ubuntu%2022.04-orange)
![Python](https://img.shields.io/badge/Python-3.10-green)
![Node.js](https://img.shields.io/badge/Node.js-20%20(LTS)-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

**一个 100% 复刻 GitHub Actions 体验的私有化容器平台。**
**内置 Chrome、Playwright、Python 和 Node.js，专为复杂的自动化签到与爬虫任务设计。**

</div>

---

## 📖 项目介绍

**FluxTask** 是一个基于 Docker 的任务调度系统，它解决了公共 CI/CD 服务（如 GitHub Actions）IP 地址容易被风控的问题。

与传统的轻量级 Cron 容器不同，FluxTask 采用 **“全能型” (All-in-One)** 架构。它基于 Ubuntu 22.04 构建，预装了现代自动化所需的一切环境，让你可以像在本地电脑或 GitHub Actions 虚拟机中一样，无缝运行复杂的浏览器自动化脚本。

### ✨ 核心特性

*   **🐳 全能环境**：基于 Ubuntu 22.04，内置 **Python 3.10**、**Node.js 20**、**Google Chrome** 和 **Playwright** 全套内核。
*   **🧠 双引擎支持**：智能识别脚本语言。既可以跑 Python (`pip`), 也可以跑 Node.js (`npm`)。
*   **🛡️ 私有化部署**：部署在自己的服务器或 NAS 上，拥有独享的洁净 IP，彻底告别 IP 风控。
*   **📝 实时结构化日志**：完美复刻 GitHub Actions 的日志 UI。分步骤展示（Setup -> Install -> Run），支持实时刷新，状态一目了然。
*   **🤖 自动化闭环**：脚本可以通过内置 API **反向更新面板 Secrets**。例如：脚本自动过验证码获取新 Cookie 后，直接更新数据库，无需人工干预。
*   **🎭 智能反爬虫**：支持 **Random Delay (随机延时)**，模拟真人操作时间。
*   **📦 依赖自动管理**：为每个脚本创建独立的虚拟环境 (venv/node_modules)，依赖互不冲突。

---

## 🚀 部署指南

### 1. 准备工作
确保你的服务器已安装 Docker 和 Docker Compose。

### 2. 创建 `docker-compose.yml`
新建一个目录（如 `fluxtask`），并在其中创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  fluxtask:
    # 替换为你构建的镜像地址
    image: ghcr.io/yourusername/fluxtask:latest
    container_name: fluxtask
    restart: unless-stopped
    ports:
      - "8080:8000"  # 访问端口
    volumes:
      # ⚠️ 重要：必须挂载数据目录，否则重启后数据丢失！
      - ./data:/app/data        # 数据库、虚拟环境、依赖缓存
      - ./scripts:/app/scripts  # 脚本文件
    environment:
      - TZ=Asia/Shanghai
      # 数据库文件路径 (建议保持默认)
      - DATABASE_URL=sqlite:////app/data/fluxtask.db
      # 自定义管理员账号
      - ADMIN_USER=admin
      - ADMIN_PASSWORD=admin
      # JWT 密钥 (生产环境请修改)
      - JWT_SECRET=change_this_to_a_long_random_string
```

### 3. 启动服务
```bash
docker-compose up -d
```

访问 `http://ip:8080`，使用默认账号 `admin/admin` 登录。

---

## 💻 脚本编写指南

FluxTask 支持两种语言模式，系统会自动根据代码特征识别。

### 🐍 模式 A: Python (默认)

直接编写 Python 代码即可。

*   **代码示例**：
    ```python
    import os
    from loguru import logger
    
    # 读取环境变量
    key = os.environ.get("MY_SECRET_KEY")
    logger.info(f"Task started with key: {key}")
    ```
*   **依赖管理**：在右侧 **“依赖”** 标签页填写 `requirements.txt` 内容，例如：
    ```text
    requests==2.31.0
    selenium
    playwright
    ```

### 🟢 模式 B: Node.js

在代码**第一行**添加魔法注释 `// runtime: node`。

*   **代码示例**：
    ```javascript
    // runtime: node
    const axios = require('axios');
    
    console.log("Hello from Node.js!");
    console.log("Secret:", process.env.MY_SECRET_KEY);
    ```
*   **依赖管理**：在右侧 **“依赖”** 标签页填写 npm 包名（空格或换行分隔），例如：
    ```text
    axios
    playwright
    dayjs
    ```

---

## 🌐 浏览器自动化 (Selenium / Playwright)

由于是 Docker 无头环境，使用浏览器时必须添加特定的启动参数。

### Python Playwright 示例 (推荐)
镜像已内置 Playwright 驱动，无需安装，直接使用。

```python
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # 必须添加 args=['--no-sandbox']
        browser = p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        page = browser.new_page()
        page.goto("https://www.google.com")
        print(page.title())
        browser.close()

if __name__ == "__main__":
    run()
```

### Python Selenium 示例
镜像已内置 Google Chrome Stable。

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
# ⚠️ Docker 环境必备参数，否则会崩溃
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=options)
# ...
```

---

## 🔐 进阶：脚本自动更新 Secrets

FluxTask 允许脚本反向更新面板的 Secrets（例如：自动过验证码后更新 Cookie）。系统会在脚本运行时自动注入 `FLUX_API_URL` 和 `FLUX_TOKEN`。

**Python 示例：**

```python
import os
import requests

def update_panel_cookie(new_cookie):
    api_url = os.environ.get('FLUX_API_URL')
    token = os.environ.get('FLUX_TOKEN')
    
    if api_url and token:
        try:
            requests.post(
                f"{api_url}/api/secrets",
                json={"key": "JD_COOKIE", "value": new_cookie},
                headers={"Authorization": f"Bearer {token}"},
                proxies={"http": None, "https": None} # 关键：绕过系统代理
            )
            print("✅ 面板 Cookie 已自动更新")
        except Exception as e:
            print(f"❌ 更新失败: {e}")

# 你的业务逻辑...
update_panel_cookie("pt_key=new_value;...")
```

---

## ❓ 常见问题 (FAQ)

**Q: 为什么重启容器后任务都消失了？**
A: 你没有挂载 `volumes`。请检查 `docker-compose.yml` 中是否包含了 `- ./data:/app/data`。数据文件存储在 `/app/data/fluxtask.db`。

**Q: 浏览器启动报错 `session not created: Chrome instance exited`**
A: 这是因为 Docker 共享内存不足。请务必在启动参数中添加 `--disable-dev-shm-usage`。

**Q: 依赖安装时提示 HTML 警告？**
A: 系统默认使用阿里云/清华源加速。这是 `pip` 对国内镜像源 HTML 格式的警告，**完全不影响使用**，请忽略。

**Q: 如何手动安装系统级依赖？**
A: 镜像基于 Ubuntu 22.04。你可以在 Python 脚本中使用 `subprocess.run(["apt-get", "install", "-y", "..."])` 来临时安装（需要 root 权限，容器默认是 root），但建议将通用依赖加入 `Dockerfile` 重新构建。



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
