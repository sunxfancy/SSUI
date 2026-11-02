import os
import sys
import yaml
from pathlib import Path
from contextlib import contextmanager
import tempfile


def add_extension_paths():
    """把扩展目录及其 vendor/ 根目录加入 sys.path。

    返回实际加入的路径列表。扩展的 ``ssui_*`` SDK 包与第三方 vendored
    代码（cosyvoice / matcha / trellis / stdgen 等）都通过这里导入。

    注意：只加入 vendor/ 根目录而不是其子目录，避免 vendored 包内部的
    子包（如 matcha/onnx）冒充同名顶层模块并遮蔽真实依赖（如 pip 的 onnx）。
    """
    extensions_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "extensions")
    )
    added = []
    if not os.path.isdir(extensions_dir):
        return added
    for ext in os.listdir(extensions_dir):
        ext_dir = os.path.join(extensions_dir, ext)
        if not os.path.isdir(ext_dir):
            continue
        if ext_dir not in sys.path:
            sys.path.insert(0, ext_dir)
            added.append(ext_dir)
        vendor_dir = os.path.join(ext_dir, "vendor")
        if os.path.isdir(vendor_dir):
            if vendor_dir not in sys.path:
                sys.path.insert(0, vendor_dir)
                added.append(vendor_dir)
    return added

# 检查是否应该运行真实模型测试（默认关闭，需要下载 GB 级模型）
def should_run_model_tests() -> bool:
    return os.environ.get("SSUI_RUN_MODEL_TESTS", "0").lower() in ("1", "true", "yes")


# Deprecated alias，保持向后兼容
def should_run_slow_tests() -> bool:
    return should_run_model_tests()

# 获取测试数据根目录
def get_test_data_dir() -> Path:
    # 从环境变量获取，或使用默认位置
    return Path(os.environ.get("TEST_DATA_DIR", os.path.expanduser("~/.ssui_test_data")))

def _load_manifest():
    manifest_path = Path(__file__).parent / "model_manifest.yaml"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# 按需下载模型（依据 tests/model_manifest.yaml，写入 TEST_DATA_DIR）
def download_if_needed(model_key: str, sub_key: str | None = None) -> Path:
    manifest = _load_manifest()
    entry = manifest[model_key] if sub_key is None else manifest[model_key][sub_key]
    data_dir = get_test_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    if "local" in entry:
        local_path = data_dir / entry["local"]
        if not local_path.exists():
            print(f"警告: 本地模型不存在，请手动放置: {local_path}")
        return local_path

    if entry.get("snapshot"):
        import huggingface_hub

        local_dir = data_dir / model_key
        if sub_key:
            local_dir = local_dir / sub_key
        huggingface_hub.snapshot_download(
            entry["repo"],
            revision=entry.get("revision", "main"),
            local_dir=str(local_dir),
            allow_patterns=entry.get("allow_patterns"),
        )
        return local_dir

    dest_path = data_dir / entry["file"]
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    from tests.download_models import _download_file
    _download_file(entry, dest_path)
    for extra in entry.get("extra_files", []):
        extra_entry = {**entry, "file": extra, "sha256": ""}
        _download_file(extra_entry, data_dir / extra)

    if entry.get("return_dir"):
        return data_dir / entry["return_dir"]
    return dest_path



@contextmanager
def model_output_dir(name: str):
    """Optionally retain real inference artifacts for inspection."""
    root = os.environ.get("SSUI_MODEL_OUTPUT_DIR")
    if root:
        dest = Path(root).resolve() / name
        dest.mkdir(parents=True, exist_ok=True)
        yield str(dest)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp
