#!/usr/bin/env bash
# Run a model/build with the workspace-local CUDA toolchain.
set -euo pipefail
SSUI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$SSUI_ROOT/.venv/native-cuda/runtime.json" ]]; then
    exec "$SSUI_ROOT/.venv/bin/python" "$SSUI_ROOT/dependencies/native_cuda.py" exec -- "$@"
fi
SSUI_NATIVE_PREFIX="${SSUI_NATIVE_PREFIX:-$SSUI_ROOT/.build/cuda-env}"
export TMPDIR="$SSUI_ROOT/.build/tmp"
export MAMBA_ROOT_PREFIX="$SSUI_ROOT/.build/mamba"
export XDG_CACHE_HOME="$SSUI_ROOT/.build/cache"
export HF_HOME="$SSUI_ROOT/.build/cache/huggingface"
export U2NET_HOME="$SSUI_ROOT/.build/cache/u2net"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export TORCH_EXTENSIONS_DIR="$SSUI_ROOT/.build/torch-extensions"
export CUDA_HOME="$SSUI_NATIVE_PREFIX"
export MAX_JOBS="${MAX_JOBS:-1}"
export CPLUS_INCLUDE_PATH="$SSUI_NATIVE_PREFIX/targets/x86_64-linux/include${CPLUS_INCLUDE_PATH:+:$CPLUS_INCLUDE_PATH}"
for SSUI_HEADER_DIR in "$SSUI_ROOT"/.venv/lib/python*/site-packages/nvidia/*/include; do
    if [[ -d "$SSUI_HEADER_DIR" ]]; then
        export CPLUS_INCLUDE_PATH="$CPLUS_INCLUDE_PATH:$SSUI_HEADER_DIR"
    fi
done
export CPATH="$CPLUS_INCLUDE_PATH${CPATH:+:$CPATH}"
mkdir -p "$TMPDIR" "$TORCH_EXTENSIONS_DIR"
exec "$SSUI_ROOT/.build/tool-bootstrap/bin/micromamba" run -p "$SSUI_NATIVE_PREFIX" "$@"
