# --- 第一阶段：前端构建 (保持不变) ---
FROM node:18-alpine as frontend-builder
WORKDIR /build
RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- 第二阶段：后端运行 (基于 Ubuntu 22.04，复刻 GH Actions 环境) ---
FROM ubuntu:22.04

# 1. 基础环境变量配置
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8

WORKDIR /app

# 2. 换源并安装 Python、Chrome 及所有底层依赖
# 我们直接安装 chrome-stable，它会自动拉取所有需要的 .so 库
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg2 \
    ca-certificates \
    software-properties-common \
    git \
    tzdata \
    unzip \
    # 安装 Python 3.10
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    # 安装 Chrome 所需的核心图形库 (解决 127 错误的关键)
    libnss3 \
    libgconf-2-4 \
    libxi6 \
    libglib2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libappindicator1 \
    libasound2 \
    libatk1.0-0 \
    libgtk-3-0 \
    libgbm1 \
    fonts-liberation \
    xdg-utils \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    # --- 安装 Google Chrome ---
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    # 建立 python 命令软链接
    && ln -s /usr/bin/python3 /usr/bin/python \
    # 清理垃圾减小体积
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装后端 Python 依赖
COPY backend/requirements.txt .
# 升级 pip 并安装依赖
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# 4. 复制后端代码
COPY backend/app /app/app

# 5. 复制前端构建产物
COPY --from=frontend-builder /build/dist /app/static

# 6. 创建必要目录
RUN mkdir -p /app/data /app/scripts /app/data/venvs

# 环境变量设置
ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/fluxtask.db"

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
