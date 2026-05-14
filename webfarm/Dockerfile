# WebFarm Dockerfile
# 多阶段构建，优化镜像体积

# ========== 阶段 1: 构建前端 ==========
FROM node:18-alpine AS frontend-builder

WORKDIR /app

# 复制前端源码
COPY src/ ./src/

# 安装 http-server 用于预览
RUN npm install -g http-server

# ========== 阶段 2: Python 后端 ==========
FROM python:3.11-alpine AS backend

WORKDIR /app

# 安装系统依赖
RUN apk add --no-cache gcc musl-dev

# 安装 Python 依赖
RUN pip install --no-cache-dir aiohttp aiohttp-cors

# 复制后端代码
COPY server/ ./server/
COPY data/ ./data/

# 创建 dist 目录（用于挂载前端）
RUN mkdir -p /app/dist

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["python", "server/server.py"]

# ========== 阶段 3: 完整镜像 ==========
FROM python:3.11-alpine AS production

WORKDIR /app

# 安装系统依赖
RUN apk add --no-cache gcc musl-dev

# 安装 Python 依赖
RUN pip install --no-cache-dir aiohttp aiohttp-cors

# 复制后端代码
COPY server/ ./server/
COPY data/ ./data/

# 复制前端（预构建）
COPY src/ ./dist/

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/api/farm?user_id=health || exit 1

# 启动命令
CMD ["python", "server/server.py"]
