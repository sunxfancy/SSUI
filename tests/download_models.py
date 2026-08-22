#!/usr/bin/env python
"""按 tests/model_manifest.yaml 下载真模型回归所需的测试模型。

用法：
    python tests/download_models.py --all
    python tests/download_models.py sd1 flux

文件写入 $TEST_DATA_DIR（默认 ~/.ssui_test_data）。
"""

import argparse
import os
from pathlib import Path

import requests
import yaml
from tqdm import tqdm


MANIFEST_PATH = Path(__file__).parent / "model_manifest.yaml"


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def data_dir() -> Path:
    return Path(os.environ.get("TEST_DATA_DIR", os.path.expanduser("~/.ssui_test_data")))


def _download_file(entry, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"已存在，跳过: {dest}")
        return

    url = (
        f"https://huggingface.co/{entry['repo']}/resolve/"
        f"{entry.get('revision', 'main')}/{entry['file']}"
    )
    print(f"下载: {url}")
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(dest, "wb") as f, tqdm(
            total=int(response.headers.get("content-length", 0)),
            unit="B",
            unit_scale=True,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    sha256 = entry.get("sha256") or ""
    if sha256:
        import hashlib

        actual = hashlib.sha256(dest.read_bytes()).hexdigest()
        if actual != sha256:
            raise RuntimeError(f"sha256 校验失败: {dest}")
        print(f"sha256 校验通过: {dest}")
    else:
        print(f"警告: 清单未提供 sha256，跳过校验: {dest}")


def _download_snapshot(entry, dest: Path):
    import huggingface_hub

    dest.mkdir(parents=True, exist_ok=True)
    huggingface_hub.snapshot_download(
        entry["repo"],
        revision=entry.get("revision", "main"),
        local_dir=str(dest),
    )
    print(f"快照下载完成: {dest}")


def download_entry(model_key, sub_key=None):
    manifest = load_manifest()
    entry = manifest[model_key] if sub_key is None else manifest[model_key][sub_key]
    base = data_dir()

    if "local" in entry:
        local_path = base / entry["local"]
        if local_path.exists():
            print(f"本地模型已存在: {local_path}")
        else:
            print(f"跳过（需手动放置）: {local_path} —— {entry.get('note', '')}")
        return local_path

    if entry.get("snapshot"):
        dest = base / model_key
        if sub_key:
            dest = dest / sub_key
        _download_snapshot(entry, dest)
        return dest

    dest = base / entry["file"]
    _download_file(entry, dest)
    return dest


def main():
    parser = argparse.ArgumentParser(description="下载真模型测试数据")
    parser.add_argument("keys", nargs="*", help="要下载的模型 key；--all 表示全部")
    parser.add_argument("--all", action="store_true", help="下载清单中全部模型")
    args = parser.parse_args()

    manifest = load_manifest()
    keys = manifest.keys() if args.all else args.keys
    if not keys:
        parser.error("请指定模型 key 或使用 --all")

    for key in keys:
        if key not in manifest:
            print(f"未知模型 key: {key}")
            continue
        entry = manifest[key]
        if isinstance(entry, dict) and any(
            isinstance(v, dict) for v in entry.values()
        ):
            for sub_key in entry:
                download_entry(key, sub_key)
        else:
            download_entry(key)


if __name__ == "__main__":
    main()
