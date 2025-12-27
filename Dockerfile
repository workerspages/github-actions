# --- Stage 1: 前端构建 (保持不变) ---
FROM node:18-alpine as frontend-builder
WORKDIR /build
RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Stage 2: 后端运行 (全能型环境：Ubuntu + Python + Node.js + Chrome) ---
FROM ubuntu:22.04

# 1. 基础环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8

WORKDIR /app

# 2. 安装系统基础 + Python + Chrome依赖 + 常用工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg2 ca-certificates software-properties-common \
    git tzdata unzip zip jq build-essential \
    # Python 环境
    python3 python3-pip python3-venv python3-dev \
    # Chrome 核心依赖库
    libnss3 libgconf-2-4 libxi6 libglib2.0-0 \
    libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libxrender1 libxss1 libxtst6 \
    libappindicator1 libasound2 libatk1.0-0 libgtk-3-0 libgbm1 \
    fonts-liberation xdg-utils \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    # --- 3. 安装 Node.js 20 (LTS) ---
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    # --- 4. 安装 Google Chrome ---
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    # 建立 python 软链接
    && ln -s /usr/bin/python3 /usr/bin/python \
    # 清理缓存
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 5. 配置 npm 淘宝源 (加速 Node 依赖安装)
RUN npm config set registry https://registry.npmmirror.com

# 6. 安装 Python 基础依赖
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# 7. 复制程序代码
COPY backend/app /app/app
COPY --from=frontend-builder /build/dist /app/static

# 8. 创建数据目录
RUN mkdir -p /app/data /app/scripts /app/data/venvs

ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/fluxtask.db"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
