import os
import sys
import hashlib
import requests
import yaml
from pathlib import Path
from tqdm import tqdm


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
        )
        return local_dir

    dest_path = data_dir / entry["file"]
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if not dest_path.exists() or dest_path.stat().st_size == 0:
        print(f"下载模型: {dest_path}")
        url = (
            f"https://huggingface.co/{entry['repo']}/resolve/"
            f"{entry.get('revision', 'main')}/{entry['file']}"
        )
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with open(dest_path, "wb") as f, tqdm(
            total=total_size, unit="B", unit_scale=True
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

        sha256 = entry.get("sha256") or ""
        if sha256:
            actual = hashlib.sha256(dest_path.read_bytes()).hexdigest()
            if actual != sha256:
                raise RuntimeError(f"sha256 校验失败: {dest_path}")
    else:
        print(f"模型已存在: {dest_path}")

    for extra in entry.get("extra_files", []):
        extra_path = data_dir / extra
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        if not extra_path.exists() or extra_path.stat().st_size == 0:
            url = (
                f"https://huggingface.co/{entry['repo']}/resolve/"
                f"{entry.get('revision', 'main')}/{extra}"
            )
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(extra_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

    if entry.get("return_dir"):
        return data_dir / entry["return_dir"]
    return dest_path

