import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Body, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask

from server.models import ModelInfo, ScanModelsRequest
from server.opener_service import FileOpenerManager

router = APIRouter()


@router.get("/config/")
async def get_config(request: Request):
    return request.app.state.config_service.get_config()


@router.post("/config/")
async def config(request: Request, config: Dict[str, Any]):
    return request.app.state.config_service.update_config(config)


@router.post("/config/scan_models/{client_id}")
async def scan_models(request: Request, client_id: str, payload: ScanModelsRequest):
    scan_dir = os.path.normpath(payload.scan_dir)
    print("scan_models", client_id, scan_dir)
    if not os.path.exists(scan_dir):
        return {"error": "Scan directory not found"}

    request_uuid = str(uuid.uuid4())
    model_service = request.app.state.model_service
    websocket_service = request.app.state.websocket_service

    return JSONResponse(
        content=jsonable_encoder(
            {
                "type": "start",
                "request_uuid": request_uuid,
                "callbacks": ["model_found"],
            }
        ),
        background=BackgroundTask(
            model_service.scan_models,
            scan_dir=scan_dir,
            client_id=client_id,
            request_uuid=request_uuid,
            callback=websocket_service.send_callback,
            finish_callback=websocket_service.send_finish,
        ),
    )


@router.post("/config/install_model")
async def install_model(
    request: Request,
    model_path: str = Body(..., embed=True),
    create_softlink: bool = Body(False, embed=True),
):
    model_service = request.app.state.model_service
    config_service = request.app.state.config_service
    result = await model_service.install_model(model_path, create_softlink)
    if "type" in result and result["type"] == "success":
        model_info = ModelInfo(**result)
        config_service.add_installed_model(model_info)
    return result


@router.get("/config/opener/{file_extension}")
async def opener(file_extension: str):
    return FileOpenerManager.instance().get_opener(file_extension)


@router.get("/config/opener")
async def opener_all():
    return FileOpenerManager.instance().get_all_openers()
