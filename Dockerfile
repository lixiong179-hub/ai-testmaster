# =============================================================
# AI测试平台 - 多阶段 Docker 构建
# 阶段1: 前端构建 (Node.js)
# 阶段2: 后端运行时 (Python + Playwright)
# =============================================================

# -------------------- 阶段1: 前端构建 --------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app

# 先复制依赖描述文件，利用 Docker 缓存层加速构建
COPY package.json package-lock.json* ./

# 安装前端依赖
RUN npm ci --prefer-offline

# 复制前端源码并构建
COPY . .
RUN npm run build

# -------------------- 阶段2: 后端运行时 --------------------
FROM python:3.11-slim AS backend

WORKDIR /app

# 安装 Playwright 所需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg2 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libx11-xcb1 && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器（仅 Chromium，用于 UI 自动化测试执行）
RUN playwright install chromium --with-deps || true

# 复制后端源码
COPY . .

# 从前端构建阶段复制静态产物
COPY --from=frontend-build /app/dist /app/dist

# 创建上传目录
RUN mkdir -p /app/uploads

EXPOSE 8000

# 生产环境启动命令：4 worker 进程
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
