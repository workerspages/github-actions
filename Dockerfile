# --- Stage 1: 前端构建 (保持不变) ---
FROM node:18-alpine as frontend-builder
WORKDIR /build
RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Stage 2: 后端运行 (全能环境) ---
FROM ubuntu:22.04

# 1. 基础环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
# 确保本地 bin 目录在 PATH 中 (防止 pip 安装后找不到命令)
ENV PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

WORKDIR /app

# 2. 安装基础工具 + Python + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg2 ca-certificates software-properties-common \
    git tzdata unzip zip jq build-essential \
    python3 python3-pip python3-venv python3-dev \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    # 安装 Node.js 20 (LTS)
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    # 建立 python 软链接
    && ln -s /usr/bin/python3 /usr/bin/python \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. 安装 Python 依赖
COPY backend/requirements.txt .

# === 关键修改 ===
# 1. 升级 pip
# 2. 显式安装 playwright 库 (解决 127 错误)
# 3. 安装 requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 install --no-cache-dir playwright -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 【核心步骤】安装 Playwright 浏览器内核及系统依赖
# 现在 playwright 命令一定存在了
RUN playwright install --with-deps

# 5. 安装 Google Chrome + ChromeDriver (与 GitHub Actions 官方环境一致)
# 安装 Xvfb 虚拟显示服务器，允许非 headless 模式运行
# 5. 安装 Google Chrome + ChromeDriver (与 GitHub Actions 官方环境一致)
# 安装 Xvfb 虚拟显示服务器，允许非 headless 模式运行
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb wget ca-certificates \
    # 直接下载并安装 Google Chrome (让 apt 自动解决依赖)
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装匹配版本的 ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+') \
    && CHROME_MAJOR=${CHROME_VERSION%%.*} \
    && echo "Chrome version: $CHROME_VERSION (major: $CHROME_MAJOR)" \
    && DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}") \
    && echo "ChromeDriver version: $DRIVER_VERSION" \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm -rf /tmp/chromedriver* \
    # 安装 Selenium 相关 Python 包
    && pip3 install --no-cache-dir selenium webdriver-manager -i https://pypi.tuna.tsinghua.edu.cn/simple

# 设置 Chrome 环境变量 (与 GitHub Actions 一致)
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
# Xvfb 显示配置
ENV DISPLAY=:99

# 6. 复制程序代码
COPY backend/app /app/app
COPY --from=frontend-builder /build/dist /app/static

# 7. 创建数据目录
RUN mkdir -p /app/data /app/scripts /app/data/venvs

ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/github-actions.db"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
