#!/bin/bash

# 检查操作系统类型
OS_TYPE=$(uname)
ARCHITECTURE=$(uname -m)
PYTHON_VERSION="3.12.8"
RELEASE_DATE="20241219"

# 检查系统是 Linux 或 macOS
if [[ "$OS_TYPE" != "Linux" && "$OS_TYPE" != "Darwin" ]]; then
    echo "Unsupported OS!"
    exit 1
fi

# 检查处理器架构
if [[ "$ARCHITECTURE" == "x86_64" ]]; then
    ARCH="x86_64-unknown-linux-gnu"
elif [[ "$ARCHITECTURE" == "aarch64" ]]; then
    ARCH="aarch64-unknown-linux-gnu"
elif [[ "$ARCHITECTURE" == "arm64" && "$OS_TYPE" == "Darwin" ]]; then
    ARCH="aarch64-apple-darwin"
elif [[ "$ARCHITECTURE" == "x86_64" && "$OS_TYPE" == "Darwin" ]]; then
    ARCH="x86_64-apple-darwin"
else
    echo "Unsupported architecture!"
    exit 1
fi

# 设置下载链接
DOWNLOAD_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_DATE}/cpython-${PYTHON_VERSION}+${RELEASE_DATE}-${ARCH}-install_only_stripped.tar.gz"

# 创建.build文件夹并将Python放入其中
mkdir -p .build

echo "Extracting Python..."
# 下载并解压Python
echo "Downloading Python from ${DOWNLOAD_URL}..."
curl -L "${DOWNLOAD_URL}" -o .build/python.tar.gz

cd .build && tar -xzf python.tar.gz && rm python.tar.gz
cd ..

# 使用venv创建虚拟环境
echo "Creating virtual environment..."
.build/python/bin/python3 -m venv .build/base

# 激活虚拟环境并安装依赖
echo "Installing dependencies from requirements.txt..."
.build/base/bin/pip install --no-deps -r .build/requirements.txt

# 创建符号链接
rm -f .venv
ln -s .build/base .venv

echo "Installation complete!" 