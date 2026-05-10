FROM python:3.10-slim

LABEL maintainer="Ulysses"
LABEL description="恋爱至上主义区域 - NxSiran Telegram Bot v0.1"
LABEL version="0.1.0"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir chromadb lightrag-hku edge-tts

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /opt/NxSiran/data

# 环境变量
ENV DATA_DIR=/opt/NxSiran/data
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# 启动
CMD ["python3", "bot.py"]
