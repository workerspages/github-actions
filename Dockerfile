# --- Stage 1: 前端构建 (保持不变) ---
FROM node:18-alpine AS frontend-builder
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
ENV PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

WORKDIR /app

# 2. 安装基础工具 + Python + Node.js + tini (修复#1: 使用 tini 接管 PID 1 僵尸进程回收)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg2 ca-certificates software-properties-common \
    git tzdata unzip zip jq build-essential \
    tini \
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

RUN pip3 install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 install --no-cache-dir playwright -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 安装 Playwright 浏览器内核及系统依赖
# 修复: ARM64 下 QEMU 模拟时 playwright install --with-deps 会因 ldconfig
#       在 QEMU 中触发 SIGSEGV 导致 libc-bin 配置失败。
# 解决策略:
#   - amd64: 原生执行，保持 --with-deps chromium
#   - arm64: 跳过 --with-deps，改用第5步安装的系统 chromium-browser
#            并通过 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD + 软链接让 playwright 找到浏览器
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        echo "[amd64] playwright install --with-deps chromium" \
        && playwright install --with-deps chromium; \
    else \
        echo "[arm64] Skipping playwright --with-deps to avoid QEMU/ldconfig SIGSEGV" \
        && playwright install chromium || true; \
    fi

# 5. 安装浏览器 (支持多架构)
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb wget ca-certificates \
    && if [ "$TARGETARCH" = "amd64" ]; then \
        echo "Installing Google Chrome for AMD64..." \
        && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb \
        && apt-get install -y /tmp/chrome.deb \
        && rm /tmp/chrome.deb \
        && CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+') \
        && CHROME_MAJOR=${CHROME_VERSION%%.*} \
        && DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}") \
        && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
        && unzip /tmp/chromedriver.zip -d /tmp \
        && mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
        && chmod +x /usr/bin/chromedriver \
        && rm -rf /tmp/chromedriver*; \
    else \
        echo "Installing Chromium for ARM64/Other..." \
        && apt-get install -y --no-install-recommends chromium-browser chromium-chromedriver \
        && ln -sf /usr/bin/chromium-browser /usr/bin/google-chrome \
        && ln -sf /usr/bin/chromium-chromedriver /usr/bin/chromedriver; \
    fi \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir selenium webdriver-manager -i https://pypi.tuna.tsinghua.edu.cn/simple

# 6. ARM64: 让 Playwright 优先使用系统 chromium-browser
#    通过环境变量告知 playwright 可执行文件路径（跳过内置浏览器查找）
RUN if [ "$TARGETARCH" != "amd64" ] && [ -f /usr/bin/chromium-browser ]; then \
        PLAYWRIGHT_DIR=$(python3 -c "import playwright; import os; print(os.path.dirname(playwright.__file__))") \
        && CHROMIUM_DIR=$(find /root/.cache/ms-playwright -name "chrome" -type f 2>/dev/null | head -1 | xargs dirname 2>/dev/null || true) \
        && if [ -z "$CHROMIUM_DIR" ]; then \
            mkdir -p /root/.cache/ms-playwright/chromium-system/chrome-linux \
            && ln -sf /usr/bin/chromium-browser /root/.cache/ms-playwright/chromium-system/chrome-linux/chrome \
            && echo "ARM64: symlinked system chromium into playwright cache"; \
        fi; \
    fi

# 设置环境变量
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV DISPLAY=:99
# ARM64: 允许 playwright 使用系统已安装的浏览器
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# 7. 复制程序代码
COPY backend/app /app/app
COPY --from=frontend-builder /build/dist /app/static

# 8. 创建数据目录
RUN mkdir -p /app/data /app/scripts /app/data/venvs

ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/data/github-actions.db"

EXPOSE 8000

# 修复#1: 使用 tini 作为 PID 1 入口，负责回收僵尸子进程。直接以 uvicorn 作为 PID 1 无法处理子进程回收。
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
