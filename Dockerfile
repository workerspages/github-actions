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

# 5. 复制程序代码
COPY backend/app /app/app
COPY --from=frontend-builder /build/dist /app/static

# 6. 创建数据目录
RUN mkdir -p /app/data /app/scripts /app/data/venvs

ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/github-actions.db"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
