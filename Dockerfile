# 构建阶段
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 as builder

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装 Python 3.12
RUN apt update && apt install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt update \
    && apt install -y \
    python3.12 \
    python3-pip \
    python3.12-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js 22
ENV NVM_DIR /usr/local/nvm
RUN mkdir -p $NVM_DIR \
    && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash \
    && . $NVM_DIR/nvm.sh && nvm install 22 && nvm use 22 \
    && corepack enable yarn && node -v && yarn -v

# 设置工作目录
WORKDIR /app

# 创建 .dockerignore 文件
RUN echo "__pycache__\n*.pyc\n*.pyo\n*.pyd\n.Python\nenv\npip-log.txt\npip-delete-this-directory.txt\n.tox\n.coverage\n.coverage.*\n.cache\nnosetests.xml\ncoverage.xml\n*.cover\n*.log\n.pytest_cache\n.env\n.venv\nvenv\nENV\nnode_modules\ndist\nbuild\n*.egg-info\n.installed.cfg\n*.egg" > .dockerignore

# 复制必要的项目文件
COPY ssui/ ssui/
COPY ss_executor/ ss_executor/
COPY server/ server/
COPY frontend/ frontend/
COPY extension_builder/ extension_builder/
COPY extensions/ extensions/
COPY dependencies/ dependencies/
COPY backend/ backend/
COPY package.json package.json
COPY yarn.lock yarn.lock


# 创建并激活 Python 虚拟环境
RUN python3.12 -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 安装 Python 依赖
RUN pip install uv
RUN uv pip install --no-cache-dir -r /app/dependencies/requirements-linux.txt


# 安装 Node.js 依赖
ENV SSUI_CI_SKIP_INSTALL=1
RUN . $NVM_DIR/nvm.sh && yarn

# 构建前端
RUN . $NVM_DIR/nvm.sh && yarn build:frontend

# 运行阶段
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装运行时依赖
RUN apt update && apt install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt update \
    && apt install -y \
    python3.12 \
    python3-pip \
    python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 从构建阶段复制必要的目录
COPY --from=builder /app/ssui /app/ssui
COPY --from=builder /app/ss_executor /app/ss_executor
COPY --from=builder /app/server /app/server
COPY --from=builder /app/frontend/functional_ui/dist /app/frontend/functional_ui/dist
COPY --from=builder /app/extensions /app/extensions
COPY --from=builder /app/dependencies /app/dependencies
COPY --from=builder /app/backend /app/backend

RUN apt update && apt install -y ffmpeg libsm6 libxext6 


# 暴露端口
EXPOSE 7422

# 设置启动命令
CMD ["bash", "-c", "python -m ss_executor & exec python -m server --host 0.0.0.0"]
