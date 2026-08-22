import json
import os
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Body, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask

router = APIRouter()


@router.get("/api/model")
async def model(request: Request, model_path: str):
    model_path = os.path.normpath(model_path)
    meta_path = model_path + ".meta"
    data = json.load(open(meta_path, "r"))
    data["path"] = model_path
    return data


@router.get("/api/available_models")
async def available_models(request: Request):
    return request.app.state.config_service.get_installed_models()


@router.post("/api/hf_download/{client_id}")
async def hf_download(
    request: Request,
    client_id: str,
    repo_id: str = Body(..., embed=True),
    local_dir: Optional[str] = Body(None, embed=True),
):
    request_uuid = str(uuid.uuid4())
    if local_dir is None:
        local_dir = os.path.join(
            request.app.state.resources_dir, "hf_models", repo_id
        )
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    model_service = request.app.state.model_service
    websocket_service = request.app.state.websocket_service

    return JSONResponse(
        content=jsonable_encoder(
            {
                "type": "start",
                "request_uuid": request_uuid,
                "callbacks": ["download_progress"],
            }
        ),
        background=BackgroundTask(
            model_service.hf_download,
            repo_id=repo_id,
            local_dir=local_dir,
            client_id=client_id,
            request_uuid=request_uuid,
            callback=websocket_service.send_callback,
            finish_callback=websocket_service.send_finish,
        ),
    )


@router.get("/api/civitai/models")
async def civitai_models(query: str = "", type: str = "", page: int = 1, limit: int = 50):
    """Civitai 模型搜索代理：避免浏览器端 CORS，服务端透传 Civitai API。"""
    params: dict = {"page": page, "limit": min(limit, 100)}
    if query:
        params["query"] = query
    if type:
        params["types"] = type
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://civitai.com/api/v1/models", params=params)
            if resp.status_code != 200:
                return JSONResponse(
                    {"error": f"Civitai API error: {resp.status_code}"},
                    status_code=502,
                )
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": f"Civitai API request failed: {e}"}, status_code=502)


@router.get("/api/hf/models/{repo_id:path}")
async def hf_model(repo_id: str):
    """HuggingFace 单仓库信息（用于“添加仓库”）。"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"https://huggingface.co/api/models/{repo_id}")
            if resp.status_code != 200:
                return JSONResponse(
                    {"error": f"HuggingFace API error: {resp.status_code}"},
                    status_code=502,
                )
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": f"HuggingFace API request failed: {e}"}, status_code=502)


@router.get("/api/hf/models")
async def hf_models(search: str = "", limit: int = 50):
    """HuggingFace 模型搜索代理：避免浏览器端 CORS。"""
    params: dict = {
        "search": search,
        "limit": min(limit, 100),
        "sort": "downloads",
        "direction": -1,
        "full": "full",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://huggingface.co/api/models", params=params)
            if resp.status_code != 200:
                return JSONResponse(
                    {"error": f"HuggingFace API error: {resp.status_code}"},
                    status_code=502,
                )
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": f"HuggingFace API request failed: {e}"}, status_code=502)


# 团队预制的 Flux 模型下载包配图（来自原 PresetModels 设计）
FLUX_PRESET_IMAGE_URL = (
    "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/f905bc28-9db6-4f83-85ae-93c94718881d/anim=false,width=450/NfX8MYg-_nTv_PpQBNJSr.jpeg"
)

PRESET_IMAGE_URLS = {
    "FLUX Schnell (Quantized)": FLUX_PRESET_IMAGE_URL,
}


def _preset_to_dict(model) -> dict:
    base = getattr(model, "base", "")
    model_type = getattr(model, "type", "")
    return {
        "id": model.name.lower().replace(" ", "-").replace("(", "").replace(")", ""),
        "name": model.name,
        "base": base.value if hasattr(base, "value") else str(base),
        "type": model_type.value if hasattr(model_type, "value") else str(model_type),
        "source": model.source,
        "description": model.description,
        "size": model.description,
        "imageUrl": PRESET_IMAGE_URLS.get(model.name, ""),
    }


@router.get("/api/preset_models")
async def preset_models():
    """返回精选的预设模型列表（来自 backend/model_manager/starter_models.py）。"""
    from backend.model_manager import starter_models

    # 团队预制的 Flux 模型下载包（含配图），固定置于列表首位
    flux_preset = {
        "id": "001-flux-preset",
        "name": "Flux Model Preset",
        "base": "flux",
        "type": "main",
        "source": "InvokeAI/flux_schnell_quantized",
        "description": "FLUX Schnell (Quantized) · clip-vit-large-patch14 · t5_bnb_int8_quantized_encoder · Flux Vae",
        "size": "FLUX Schnell (Quantized) · clip-vit-large-patch14 · t5_bnb_int8_quantized_encoder · Flux Vae",
        "imageUrl": FLUX_PRESET_IMAGE_URL,
    }
    items = [flux_preset]

    preset_names = [
        "cyberrealistic_sd1",
        "rev_animated_sd1",
        "dreamshaper_8_sd1",
        "deliberate_sd1",
        "juggernaut_sdxl",
        "dreamshaper_sdxl",
        "flux_dev_quantized",
    ]
    for name in preset_names:
        model = getattr(starter_models, name, None)
        if model is not None:
            items.append(_preset_to_dict(model))
    return {"items": items}


@router.post("/api/preset_download/{client_id}")
async def preset_download(
    request: Request,
    client_id: str,
    name: str = Body(..., embed=True),
    source: str = Body(..., embed=True),
    base: str = Body("", embed=True),
):
    """下载预设模型：HTTP(S) 直链用 download_file，HuggingFace 仓库用 hf_download。"""
    request_uuid = str(uuid.uuid4())
    resources_dir = request.app.state.resources_dir
    safe_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip() or "model"
    local_dir = os.path.join(resources_dir, "preset_models", safe_name)
    model_service = request.app.state.model_service
    websocket_service = request.app.state.websocket_service

    if source.startswith(("http://", "https://")):
        background_task = BackgroundTask(
            model_service.download_file,
            url=source,
            local_dir=local_dir,
            client_id=client_id,
            request_uuid=request_uuid,
            callback=websocket_service.send_callback,
            finish_callback=websocket_service.send_finish,
        )
    else:
        # HuggingFace 仓库 ID：hf_download 的回调约定是 (client_id, request_uuid, name, data)
        def hf_callback(cid: str, rid: str, name: str, data: dict):
            websocket_service.send_callback(cid, rid, {name: data})

        def hf_finish(cid: str, rid: str):
            websocket_service.send_finish(cid, rid)

        background_task = BackgroundTask(
            model_service.hf_download,
            repo_id=source,
            local_dir=local_dir,
            client_id=client_id,
            request_uuid=request_uuid,
            callback=hf_callback,
            finish_callback=hf_finish,
        )

    return JSONResponse(
        content=jsonable_encoder(
            {
                "type": "start",
                "request_uuid": request_uuid,
                "callbacks": ["download_progress", "download_error"],
            }
        ),
        background=background_task,
    )
