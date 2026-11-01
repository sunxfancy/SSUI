"""ModelScope public model discovery and streamed repository downloads."""
import os
import hashlib
import re
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "https://modelscope.cn"


def validate_repo(repo_id):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo_id) or any(
        part in {".", ".."} for part in repo_id.split("/")
    ):
        raise ValueError("请输入 owner/model 格式的仓库 ID")
    return quote(repo_id, safe="/")


def unwrap(response):
    response.raise_for_status()
    payload = response.json()
    if payload.get("success") is False or payload.get("Success") is False:
        raise ValueError(payload.get("message") or payload.get("Message") or "ModelScope request failed")
    return payload.get("data", payload.get("Data", payload))


def normalize(model):
    owner = model.get("owner") or model.get("Owner") or model.get("Namespace") or ""
    if isinstance(owner, dict):
        owner = owner.get("name") or owner.get("Name") or ""
    name = model.get("name") or model.get("Name") or ""
    repo_id = model.get("id") or model.get("path") or model.get("Path") or model.get("model_id") or ""
    if "/" not in repo_id:
        repo_id = f"{owner}/{name or repo_id}"
    return {
        "id": repo_id, "modelId": repo_id, "author": owner or repo_id.split("/")[0],
        "downloads": model.get("downloads") or model.get("Downloads") or 0,
        "likes": model.get("likes") or model.get("Likes") or 0,
        "tags": model.get("tags") or [], "pipeline_tag": model.get("task") or next(iter(model.get("tasks") or []), ""),
    }


async def fetch_models(search="", limit=50, repo_id=None):
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if repo_id is not None:
            path = validate_repo(repo_id.strip())
            data = unwrap(await client.get(f"{BASE}/openapi/v1/models/{path}"))
            model = normalize(data)
            model["id"] = model["modelId"] = repo_id.strip()
            return model
        data = unwrap(await client.get(f"{BASE}/openapi/v1/models", params={
            "search": search, "page_number": 1, "page_size": max(1, min(limit, 100)),
        }))
        items = data if isinstance(data, list) else data.get("models", data.get("Models", []))
        return [normalize(item) for item in items]


def download_repository(repo_id, local_dir, report):
    repo = validate_repo(repo_id)
    root = Path(local_dir).resolve()
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        data = unwrap(client.get(f"{BASE}/api/v1/models/{repo}/repo/files", params={
            "Revision": "master", "Recursive": "true",
        }))
        files = [item for item in data["Files"] if item.get("Type") != "tree"]
        if not files:
            raise ValueError("仓库没有可下载的文件")
        total = sum(int(item.get("Size") or 0) for item in files)
        current = 0
        for item in files:
            path = item["Path"]
            target = (root / path).resolve()
            if not target.is_relative_to(root) or target == root or "\\" in path or ":" in path:
                raise ValueError("仓库包含无效文件路径")
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            digest = hashlib.sha256()
            size = 0
            with client.stream("GET", f"{BASE}/api/v1/models/{repo}/repo", params={
                "Revision": "master", "FilePath": path,
            }) as response:
                response.raise_for_status()
                with partial.open("wb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                        current += len(chunk)
                        report({"progress": min(99, current / total * 100) if total else 0,
                                "current": current, "total": total})
            if item.get("Size") is not None and size != int(item["Size"]):
                raise ValueError(f"文件下载不完整：{path}")
            if item.get("Sha256") and digest.hexdigest() != item["Sha256"]:
                raise ValueError(f"文件校验失败：{path}")
            os.replace(partial, target)
