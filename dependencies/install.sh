#!/bin/bash

# Create .venv folder
mkdir -p .venv

# Check if Python already exists
if [ ! -f ".venv/python/bin/python3" ]; then
    # Set Python version and release date
    PYTHON_VERSION="3.12.8"
    RELEASE_DATE="20241219"
    
    # Check operating system type
    OS_TYPE=$(uname -s)
    ARCHITECTURE=$(uname -m)
    
    # Set download parameters based on OS and architecture
    if [ "$OS_TYPE" = "Darwin" ]; then
        # macOS
        if [ "$ARCHITECTURE" = "x86_64" ]; then
            ARCH="x86_64-apple-darwin"
        elif [ "$ARCHITECTURE" = "arm64" ]; then
            ARCH="aarch64-apple-darwin"
        else
            echo "Unsupported architecture: $ARCHITECTURE"
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]; then
        # Linux
        if [ "$ARCHITECTURE" = "x86_64" ]; then
            ARCH="x86_64-unknown-linux-gnu"
        elif [ "$ARCHITECTURE" = "aarch64" ]; then
            ARCH="aarch64-unknown-linux-gnu"
        else
            echo "Unsupported architecture: $ARCHITECTURE"
            exit 1
        fi
    else
        echo "Unsupported operating system: $OS_TYPE"
        exit 1
    fi
    https://github.com/astral-sh/python-build-standalone/releases/download/20241219/cpython-3.12.8+20241219-${ARCH}-install_only_stripped.tar.gz
    
    # Set download URLs
    DOWNLOAD_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_DATE}/cpython-${PYTHON_VERSION}+${RELEASE_DATE}-${ARCH}-install_only_stripped.tar.gz"
    CHINA_MIRROR="https://gitee.com/Swordtooth/ssui_assets/releases/download/v0.0.2/cpython-${PYTHON_VERSION}%${RELEASE_DATE}-${ARCH}-install_only_stripped.tar.gz"

    # Download and extract Python
    echo "Downloading Python from ${DOWNLOAD_URL}..."
    if ! curl -L "${DOWNLOAD_URL}" -o .venv/python.tar.gz; then
        echo "Failed to download from primary source, trying Chinese mirror..."
        if ! curl -L "${CHINA_MIRROR}" -o .venv/python.tar.gz; then
            echo "Failed to download from Chinese mirror as well, please check your network connection or download Python manually."
            exit 1
        fi
    fi
    
    # Extract files
    tar -xzf .venv/python.tar.gz -C .venv
    rm .venv/python.tar.gz
fi

# Check if virtual environment already exists
if [ ! -f ".venv/bin/python" ]; then
    # Create virtual environment
    echo "Creating virtual environment..."
    .venv/python/bin/python3 -m venv .venv
fi

# Check and install uv tool
if [ ! -f ".venv/bin/uv" ]; then
    echo "Installing uv tool..."
    .venv/bin/python -m pip install uv==0.6.11
fi

echo "Installation completed!" 