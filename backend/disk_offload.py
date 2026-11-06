"""Opt-in disk backing for the existing partial-loading cache."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.request import Request, urlopen


def confirm_disk_offload(model, required_bytes, timeout=180):
    base = os.environ.get("SSUI_SERVER_URL", "http://localhost:7422").rstrip("/")

    def call(path, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = Request(base + "/api/resources/" + path, data=body,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    try:
        key = call("disk-requests", {"model": str(model), "required_bytes": required_bytes})["id"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            answer = call("disk-requests/" + key)["approved"]
            if answer is not None:
                if answer:
                    return
                raise MemoryError("用户拒绝磁盘 offload，已停止模型加载。")
            time.sleep(.5)
    except MemoryError:
        raise
    except Exception as exc:
        raise MemoryError("内存不足，无法取得磁盘 offload 授权；已停止加载。") from exc
    raise MemoryError("磁盘 offload 确认超时，已停止加载。")


def disk_back_model(model, required_bytes):
    """Own the backing directory for as long as the cache wrapper owns its tensors.

    mmap uses OS paging; it does not eliminate activation/working memory requirements.
    Only the state dict written by this process is loaded, with weights_only=True.
    """
    import torch
    directory = new_offload_directory(required_bytes)
    try:
        path = Path(directory.name) / "weights.pt"
        state = model.state_dict()
        if any(t.device.type != "cpu" for t in state.values()):
            raise RuntimeError("Disk backing requires a CPU model before device loading")
        torch.save(state, path)
        mapped = torch.load(path, mmap=True, weights_only=True, map_location="cpu")
        model.load_state_dict(mapped, assign=True)
        return directory
    except Exception:
        directory.cleanup()
        raise


def new_offload_directory(required_bytes):
    if sys.platform == "win32":
        cache = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        cache = Path.home() / "Library" / "Caches"
    else:
        cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    root = Path(os.environ.get("SSUI_OFFLOAD_DIR", cache / "SSUI" / "offload"))
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < required_bytes + 2**30:
        raise MemoryError("磁盘可用空间不足，无法 offload（需额外预留 1 GiB）。")
    return tempfile.TemporaryDirectory(prefix="ssui-offload-", dir=root, ignore_cleanup_errors=True)
