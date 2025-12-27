# --- Stage 1: Build Frontend ---
FROM node:18-alpine as frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Stage 2: Build Backend & Final Image ---
FROM python:3.10-slim

WORKDIR /app

# 安装基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cron curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/app /app/app

# 复制构建好的前端静态文件
COPY --from=frontend-build /app/frontend/dist /app/static

# 创建脚本存储目录和数据目录
RUN mkdir -p /app/scripts /app/data

# 环境变量
ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/fluxtask.db"

# 暴露端口
EXPOSE 8000

# 启动命令 (使用 uvicorn)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
