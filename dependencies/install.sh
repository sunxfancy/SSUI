#!/bin/bash

# 创建.venv文件夹
mkdir -p .venv

# 检查Python是否已经存在
if [ ! -f ".venv/python/bin/python3" ]; then
    # 设置Python版本和发布日期
    PYTHON_VERSION="3.12.8"
    RELEASE_DATE="20241219"
    
    # 检查操作系统类型
    OS_TYPE=$(uname -s)
    ARCHITECTURE=$(uname -m)
    
    # 根据操作系统和架构设置下载参数
    if [ "$OS_TYPE" = "Darwin" ]; then
        # macOS
        if [ "$ARCHITECTURE" = "x86_64" ]; then
            ARCH="x86_64-apple-darwin"
        elif [ "$ARCHITECTURE" = "arm64" ]; then
            ARCH="aarch64-apple-darwin"
        else
            echo "不支持的架构: $ARCHITECTURE"
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]; then
        # Linux
        if [ "$ARCHITECTURE" = "x86_64" ]; then
            ARCH="x86_64-unknown-linux-gnu"
        elif [ "$ARCHITECTURE" = "aarch64" ]; then
            ARCH="aarch64-unknown-linux-gnu"
        else
            echo "不支持的架构: $ARCHITECTURE"
            exit 1
        fi
    else
        echo "不支持的操作系统: $OS_TYPE"
        exit 1
    fi
    
    # 设置下载链接
    DOWNLOAD_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_DATE}/cpython-${PYTHON_VERSION}+${RELEASE_DATE}-${ARCH}-install_only_stripped.tar.gz"
    
    # 下载并解压Python
    echo "正在从 ${DOWNLOAD_URL} 下载Python..."
    curl -L "${DOWNLOAD_URL}" -o .venv/python.tar.gz
    
    # 解压文件
    tar -xzf .venv/python.tar.gz -C .venv
    rm .venv/python.tar.gz
fi

# 检查虚拟环境是否已经存在
if [ ! -f ".venv/bin/python" ]; then
    # 创建虚拟环境
    echo "正在创建虚拟环境..."
    .venv/python/bin/python3 -m venv .venv
fi

# 检查并安装uv工具
if [ ! -f ".venv/bin/uv" ]; then
    echo "正在安装uv工具..."
    .venv/bin/python -m pip install uv
fi

echo "安装完成！" 