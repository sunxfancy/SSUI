#!/bin/bash
set -e
VENV_DIR="${SSUI_VENV_PATH:-.venv}"

# Create .venv folder
mkdir -p "$VENV_DIR"

# Check if Python already exists
if [ ! -f "$VENV_DIR/bin/python" ] && [ ! -f "$VENV_DIR/python/bin/python3" ]; then
    # Set Python version and release date
    PYTHON_VERSION="${SSUI_PYTHON_VERSION:-3.12.8}"
    RELEASE_DATE="${SSUI_PYTHON_RELEASE:-20241219}"

    # Check operating system type
    OS_TYPE=$(uname -s)
    ARCHITECTURE=$(uname -m)

    # Set download parameters based on OS and architecture
    if [ -n "${SSUI_PYTHON_TRIPLE:-}" ]; then
        ARCH="$SSUI_PYTHON_TRIPLE"
    elif [ "$OS_TYPE" = "Darwin" ]; then
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

    # Set download URLs
    DOWNLOAD_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_DATE}/cpython-${PYTHON_VERSION}+${RELEASE_DATE}-${ARCH}-install_only_stripped.tar.gz"
    CHINA_MIRROR="https://gitee.com/Swordtooth/ssui_assets/releases/download/v0.0.2/cpython-${PYTHON_VERSION}%${RELEASE_DATE}-${ARCH}-install_only_stripped.tar.gz"

    # Download and extract Python
    echo "Downloading Python from ${DOWNLOAD_URL}..."
    if ! curl -L "${DOWNLOAD_URL}" -o "$VENV_DIR"/python.tar.gz; then
        echo "Failed to download from primary source, trying Chinese mirror..."
        if ! curl -L "${CHINA_MIRROR}" -o "$VENV_DIR"/python.tar.gz; then
            echo "Failed to download from Chinese mirror as well, please check your network connection or download Python manually."
            exit 1
        fi
    fi

    # Extract files
    tar -xzf "$VENV_DIR"/python.tar.gz -C "$VENV_DIR"
    rm "$VENV_DIR"/python.tar.gz
fi

# Check if virtual environment already exists
if [ ! -f "$VENV_DIR/bin/python" ]; then
    # Create virtual environment
    echo "Creating virtual environment..."
    "$VENV_DIR"/python/bin/python3 -m venv "$VENV_DIR"
fi

# Check and install uv tool
if [ ! -f "$VENV_DIR/bin/uv" ]; then
    echo "Installing uv tool..."
    "$VENV_DIR"/bin/python -m pip install "uv==${SSUI_UV_VERSION:-0.6.11}" packaging==24.1
fi

echo "Installation completed!"
