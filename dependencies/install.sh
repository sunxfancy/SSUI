#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .venv
# A completed venv can also be supplied by CI or a previous install.
if [ ! -x .venv/bin/python ]; then
    if [ ! -x .venv/python/bin/python3 ]; then
        case "$(uname -s):$(uname -m)" in
            Linux:x86_64) SSUI_PY_ARCH=x86_64-unknown-linux-gnu ;;
            Linux:aarch64) SSUI_PY_ARCH=aarch64-unknown-linux-gnu ;;
            Darwin:x86_64) SSUI_PY_ARCH=x86_64-apple-darwin ;;
            Darwin:arm64) SSUI_PY_ARCH=aarch64-apple-darwin ;;
            *) echo 'Unsupported OS/architecture' >&2; exit 1 ;;
        esac
        SSUI_PY_ARCHIVE=$(mktemp .venv/python.XXXXXX.tar.gz)
        trap 'rm -f "$SSUI_PY_ARCHIVE"' EXIT
        SSUI_PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241219/cpython-3.12.8+20241219-${SSUI_PY_ARCH}-install_only_stripped.tar.gz"
        curl --fail --location --retry 3 --connect-timeout 20 "$SSUI_PY_URL" -o "$SSUI_PY_ARCHIVE"
        tar -xzf "$SSUI_PY_ARCHIVE" -C .venv
        rm -f "$SSUI_PY_ARCHIVE"
        trap - EXIT
    fi
    .venv/python/bin/python3 -m venv .venv
fi
if [ ! -x .venv/bin/uv ]; then
    .venv/bin/python -m pip install uv==0.6.11 packaging==24.1
fi
.venv/bin/python --version
echo 'Python environment ready'
