# --- 前端构建阶段 ---
FROM node:18-alpine as frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
# 使用淘宝源加速(可选)
RUN npm config set registry https://registry.npmmirror.com
RUN npm install
COPY frontend/ .
RUN npm run build

# --- 后端运行阶段 (Ubuntu Base) ---
FROM ubuntu:22.04

# 设置环境变量，防止交互式安装卡住
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

WORKDIR /app

# 1. 安装基础环境 (Python, Git, Timezone)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    tzdata \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 Python 依赖
COPY backend/requirements.txt .
# Ubuntu 22.04 需要指定 pip3，并且有时需要 --break-system-packages (视具体版本而定，这里推荐创建 venv 或直接安装)
RUN pip3 install --no-cache-dir -r requirements.txt

# 3. 复制后端代码
COPY backend/app /app/app

# 4. 复制前端构建产物到静态目录
COPY --from=frontend-builder /build/dist /app/static

# 5. 创建数据和脚本目录
RUN mkdir -p /app/data /app/scripts

# 环境变量
ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/fluxtask.db"

# 端口
EXPOSE 8000

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
