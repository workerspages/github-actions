# --- Stage 1: 前端构建 ---
FROM node:18-alpine as frontend-builder
WORKDIR /build
# 使用淘宝源加速
RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Stage 2: 后端运行 (Selenium 增强版) ---
FROM python:3.10-slim

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 1. 安装系统基础工具 + Chrome + ChromeDriver 核心依赖
# 这里的 apt-get install 列表包含了 chromedriver 运行必需的库 (libnss3, libgconf, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg2 \
    ca-certificates \
    curl \
    unzip \
    git \
    tzdata \
    libnss3 \
    libgconf-2-4 \
    libxi6 \
    libglib2.0-0 \
    libx11-xcb1 \
    libxcb1 \
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
    fonts-liberation \
    xdg-utils \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    # 添加 Google Chrome 源
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    # 安装 Chrome
    && apt-get update && apt-get install -y google-chrome-stable \
    # 清理垃圾
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 复制后端代码
COPY backend/app /app/app

# 4. 复制前端产物
COPY --from=frontend-builder /build/dist /app/static

# 5. 创建目录
RUN mkdir -p /app/data /app/scripts /app/data/venvs

# 环境变量
ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/fluxtask.db"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
