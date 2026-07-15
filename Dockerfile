FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖配置
COPY pyproject.toml .

# 安装依赖（先装依赖以利用缓存）
RUN pip install --no-cache-dir -e ".[dev]"

# 复制源码
COPY src/ src/

# 重新安装（包含源码）
RUN pip install --no-cache-dir -e .

# 持久化目录（配置文件、凭据、记忆）
VOLUME /root/.harness

# 入口
ENTRYPOINT ["harness"]
CMD ["--help"]