#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
VENV_DIR="${SSUI_VENV_PATH:-.venv}"
mkdir -p "$VENV_DIR"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    if [ ! -x "$VENV_DIR/python/bin/python3" ]; then
        if [ -n "${SSUI_PYTHON_TRIPLE:-}" ]; then
            SSUI_PY_ARCH="$SSUI_PYTHON_TRIPLE"
        else
            case "$(uname -s):$(uname -m)" in
                Linux:x86_64) SSUI_PY_ARCH=x86_64-unknown-linux-gnu ;;
                Linux:aarch64) SSUI_PY_ARCH=aarch64-unknown-linux-gnu ;;
                Darwin:x86_64) SSUI_PY_ARCH=x86_64-apple-darwin ;;
                Darwin:arm64) SSUI_PY_ARCH=aarch64-apple-darwin ;;
                *) echo 'Unsupported OS/architecture' >&2; exit 1 ;;
            esac
        fi
        SSUI_PY_VERSION="${SSUI_PYTHON_VERSION:-3.12.8}"
        SSUI_PY_RELEASE="${SSUI_PYTHON_RELEASE:-20241219}"
        SSUI_PY_ARCHIVE=$(mktemp "$VENV_DIR/python.XXXXXX.tar.gz")
        trap 'rm -f "$SSUI_PY_ARCHIVE"' EXIT
        SSUI_PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${SSUI_PY_RELEASE}/cpython-${SSUI_PY_VERSION}+${SSUI_PY_RELEASE}-${SSUI_PY_ARCH}-install_only_stripped.tar.gz"
        curl --fail --location --retry 3 --connect-timeout 20 "$SSUI_PY_URL" -o "$SSUI_PY_ARCHIVE"
        tar -xzf "$SSUI_PY_ARCHIVE" -C "$VENV_DIR"
        rm -f "$SSUI_PY_ARCHIVE"
        trap - EXIT
    fi
    "$VENV_DIR/python/bin/python3" -m venv "$VENV_DIR"
fi
if [ ! -x "$VENV_DIR/bin/uv" ]; then
    "$VENV_DIR/bin/python" -m pip install "uv==${SSUI_UV_VERSION:-0.6.11}" packaging==24.1
fi
"$VENV_DIR/bin/python" --version
echo 'Python environment ready'
