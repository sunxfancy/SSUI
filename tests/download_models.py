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
    """Publish complete downloads atomically; interrupted files stay partial."""
    import hashlib

    dest.parent.mkdir(parents=True, exist_ok=True)
    expected_hash = entry.get("sha256") or ""

    def digest(path):
        value = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                value.update(chunk)
        return value.hexdigest()

    if dest.exists() and dest.stat().st_size > 0:
        if expected_hash and digest(dest) != expected_hash:
            raise RuntimeError(f"sha256 校验失败: {dest}")
        print(f"已存在，跳过: {dest}")
        return

    if entry.get("download_backend") == "hub":
        from huggingface_hub import hf_hub_download
        # The Hub cache resumes interrupted GB-scale transfers and publishes
        # completed files atomically. Keep SHA validation common to both paths.
        root = dest
        for _ in Path(entry["file"]).parts:
            root = root.parent
        downloaded = Path(hf_hub_download(
            entry["repo"], entry["file"], revision=entry.get("revision", "main"),
            local_dir=str(root),
        ))
        if expected_hash and digest(downloaded) != expected_hash:
            raise RuntimeError(f"sha256 校验失败: {downloaded}")
        return

    url = (f"https://huggingface.co/{entry['repo']}/resolve/"
           f"{entry.get('revision', 'main')}/{entry['file']}")
    partial = dest.with_name(dest.name + ".partial")
    try:
        with requests.get(url, stream=True, timeout=(20, 120)) as response:
            response.raise_for_status()
            expected_size = int(response.headers.get("content-length", 0))
            received = 0
            with partial.open("wb") as output, tqdm(
                total=expected_size or None, unit="B", unit_scale=True
            ) as progress:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        received += len(chunk)
                        progress.update(len(chunk))
            if not received or (expected_size and received != expected_size):
                raise RuntimeError(f"下载不完整: {dest} ({received}/{expected_size})")
        if expected_hash and digest(partial) != expected_hash:
            raise RuntimeError(f"sha256 校验失败: {dest}")
        os.replace(partial, dest)
    finally:
        partial.unlink(missing_ok=True)


def _download_snapshot(entry, dest: Path):
    import huggingface_hub

    dest.mkdir(parents=True, exist_ok=True)
    huggingface_hub.snapshot_download(
        entry["repo"],
        revision=entry.get("revision", "main"),
        local_dir=str(dest),
        allow_patterns=entry.get("allow_patterns"),
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
    for extra in entry.get("extra_files", []):
        extra_entry = {**entry, "file": extra, "sha256": ""}
        _download_file(extra_entry, base / extra)
    if entry.get("return_dir"):
        return base / entry["return_dir"]
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
