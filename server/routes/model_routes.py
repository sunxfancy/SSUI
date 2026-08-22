import json
import os
import uuid
from typing import Optional

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
