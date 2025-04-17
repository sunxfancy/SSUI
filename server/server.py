import datetime
import threading
from typing import Optional
import uuid
import aioshutil
import time
from fastapi import Body, FastAPI, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import torch
import torch.torch_version
import sys
import os
import json
import signal
from backend.model_manager.config import ModelType
from backend.model_manager.probe import ModelProbe
from ss_executor.model import Task
from ss_executor.scheduler import TaskScheduler
from ssui.base import Image
from pydantic_settings import BaseSettings
from contextlib import asynccontextmanager
import asyncio
from .resource_manager import ModelInfoCache

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from ss_executor import SSLoader, search_project_root
from .extensions import ExtensionManager


resources_dir: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources")
)
settings_path: str = os.path.join(resources_dir, "ssui_config.json")


class ModelInfo(BaseModel):
    path: str
    name: str
    description: str
    base_model: str
    tags: list[str]


class Settings(BaseSettings):
    host_web_ui: str = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "functional_ui", "dist"
    )
    additional_model_dirs: list[str] = []
    installed_models: list[ModelInfo] = []


settings = (
    Settings()
    if not os.path.exists(settings_path)
    else Settings.model_validate_json(open(settings_path, "r").read())
)

# 这是一个全局websocket的连接用户表
ws_clients = {}
ws_is_running = True
loop = asyncio.get_event_loop()
scheduler = TaskScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 检测扩展
    ExtensionManager.instance().detectExtensions(app)
    print("检测扩展完成")
    await scheduler.start()
    yield
    # 关闭所有连接
    print("closing scheduler and all websocket connections.")
    await scheduler.stop()
    ws_is_running = False
    for name, connection in ws_clients.items():
        await connection.close()


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:7420",
    "http://localhost:1420",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/config/")
async def config(config: dict):
    for key, value in config.items():
        if key == "additional_model_dirs":
            settings.additional_model_dirs = value
        elif key == "resources_dir":
            settings.resources_dir = value
    return {"message": "Config updated"}


def scan_target_dir(scan_dir: str, client_id: str, request_uuid: str):
    scaned_models = []
    if os.path.exists(scan_dir):
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            # 首先检查当前目录是否是一个模型
            try:
                model_config = ModelInfoCache.get(dirpath)
                if model_config:
                    # 如果当前目录是一个模型，则跳过扫描其子目录
                    scaned_models.append({"path": dirpath, "name": os.path.basename(dirpath)})
                    send_message(
                        client_id,
                        request_uuid,
                        {"find_model": {"path": dirpath, "name": os.path.basename(dirpath)}},
                    )
                    # 清空dirnames列表，这样os.walk就不会继续扫描子目录
                    dirnames.clear()
                    continue
            except Exception:
                # 如果当前目录不是模型，继续正常扫描
                pass

            for filename in filenames:
                if (
                    filename.endswith(".safetensors")
                    or filename.endswith(".pt")
                    or filename.endswith(".ckpt")
                ):
                    model_path = os.path.join(dirpath, filename)
                    # 检查模型是否已经安装，如果已安装则跳过
                    if any(
                        model.path == model_path for model in settings.installed_models
                    ):
                        print(f"跳过已安装的模型: {model_path}")
                        continue
                    try:
                        model_config = ModelInfoCache.get(model_path)
                        scaned_models.append({"path": model_path, "name": filename})
                        send_message(
                            client_id,
                            request_uuid,
                            {"find_model": {"path": model_path, "name": filename}},
                        )
                    except Exception as e:
                        continue
    send_finish(client_id, request_uuid, {"models": scaned_models})


class ScanModelsRequest(BaseModel):
    scan_dir: str = Field(description="The directory to scan for models")


@app.post("/config/scan_models/{client_id}")
async def scan_models(client_id: str, request: ScanModelsRequest):
    scan_dir = os.path.normpath(request.scan_dir)
    print("scan_models", client_id, scan_dir)
    if not os.path.exists(scan_dir):
        return {"error": "Scan directory not found"}
    request_uuid = str(uuid.uuid4())
    threading.Thread(
        target=scan_target_dir, args=(scan_dir, client_id, request_uuid), daemon=True
    ).start()
    return {
        "type": "start",
        "request_uuid": request_uuid,
        "message": "Models scan started",
        "callbacks": ["find_model"],
    }


@app.post("/config/install_model")
async def install_model(
    model_path: str = Body(..., embed=True),
    create_softlink: bool = Body(False, embed=True),
):
    model_path = os.path.normpath(model_path)
    if not os.path.exists(model_path):
        return {"error": "Model path not found"}

    model_config = ModelInfoCache.get(model_path)
    if model_config is None:
        return {"error": "Model can not be loaded"}
    tags = []
    tags.append(model_config.base)
    if model_config.type == ModelType.LoRA:
        tags.append("lora")
    elif model_config.type == ModelType.T5Encoder:
        tags.append("t5")
    elif model_config.type == ModelType.VAE:
        tags.append("vae")

    if create_softlink:
        # 创建软链接
        settings.installed_models.append(
            ModelInfo(
                path=model_path,
                name=model_config.name,
                description=model_config.description,
                base_model=model_config.base,
                tags=tags,
            )
        )
    else:
        # 复制文件
        new_model_path = os.path.join(resources_dir, model_config.name)
        await aioshutil.copy(model_path, new_model_path)
        ModelInfoCache.set(model_path, model_config)
        settings.installed_models.append(
            ModelInfo(
                path=new_model_path,
                name=model_config.name,
                description=model_config.description,
                base_model=model_config.base,
                tags=tags,
            )
        )

    # 更新配置
    json.dump(settings.model_dump(), open(settings_path, "w"))
    return {"message": "Models installed"}


@app.get("/api/version")
async def version():
    return torch.torch_version.__version__


@app.get("/api/device")
async def device():
    output = ""
    if torch.cuda.is_available():
        output = torch.cuda.get_device_name(0)
    else:
        output = "cpu"
    return output


@app.get("/api/script")
async def script(script_path: str):
    script_path = os.path.normpath(script_path)
    # project_root = search_project_root(os.path.dirname(script_path))
    # TODO: Check dependencies

    loader = SSLoader()
    loader.load(script_path)
    loader.Execute()

    def getTypeName(t):
        result = ""
        if hasattr(t, "__module__"):
            result += t.__module__ + "."
        result += t.__name__
        if hasattr(t, "__args__"):
            result += "["
            result += ", ".join([getTypeName(t) for t in t.__args__])
            result += "]"
        return result

    return {
        func.__name__: {
            "params": {param: getTypeName(param_types[param]) for param in param_types},
            "returns": (
                [getTypeName(t) for t in return_type.__args__]
                if return_type.__name__ == "tuple" or return_type.__name__ == "Tuple"
                else [getTypeName(return_type)]
            ),
        }
        for func, param_types, return_type in loader.callables
    }


@app.get("/api/model")
async def model(model_path: str):
    model_path = os.path.normpath(model_path)
    meta_path = model_path + ".meta"
    data = json.load(open(meta_path, "r"))
    data["path"] = model_path
    return data


@app.get("/api/available_models")
async def available_models():
    return settings.installed_models


# 下面是执行器相关的API

@app.post("/api/prepare")
async def prepare(script_path: str, callable: str):
    print("/api/prepare")
    print(script_path, callable)

    script_path = os.path.normpath(script_path)
    if not os.path.exists(script_path):
        return {"error": "Path not found"}
    project_root = search_project_root(os.path.dirname(script_path))
    if project_root is None:
        return {"error": "Project root not found"}

    return await scheduler.run_task(
        Task(script=script_path, callable=callable, is_prepare=True, use_sandbox=True)
    )


@app.post("/api/execute")
async def execute(script_path: str, callable: str, params: dict, details: dict):
    script_path = os.path.normpath(script_path)
    # TODO: Check dependencies

    return await scheduler.run_task(
        Task(
            script=script_path,
            callable=callable,
            params=params,
            details=details,
            is_prepare=False,
            use_sandbox=True,
        )
    )


@app.get("/file")
async def file(path: str):
    print("access file: ", path)
    if os.path.exists(path):
        if path.endswith(".png"):
            return FileResponse(path, media_type="image/png")
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            return FileResponse(path, media_type="image/jpeg")
        else:
            return FileResponse(path)
    return None


@app.get("/api/extensions")
async def extensions():
    extension_dir = {}
    for name, data in ExtensionManager.instance().extensions.items():
        extension_dir[name] = "/extension/" + name + "/dist/" + data.web_ui.dist
    return extension_dir


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    ws_clients[client_id] = websocket
    try:
        print("sending uuid to client")
        await websocket.send_text(json.dumps({"type": "uuid", "uuid": client_id}))
        while ws_is_running:
            await websocket.receive_text()  # 保持连接
    except Exception as e:
        print("client disconnected: ", e)
        ws_clients.pop(client_id, None)


async def send_text(client_id: str, message: str):
    if client_id in ws_clients:
        try:
            print("send_text: ", client_id, message)
            await ws_clients[client_id].send_text(message)
        except Exception as e:
            print("send_text error: ", e)


def send_message(client_id: str, request_uuid: str, message: dict[str, any]):
    print("send_message:", request_uuid, message)
    message = json.dumps({"type": "callback", "request_uuid": request_uuid, **message})
    loop.call_soon_threadsafe(asyncio.create_task, send_text(client_id, message))


def send_finish(
    client_id: str, request_uuid: str, message: Optional[dict[str, any]] = None
):
    print("send_finish:", request_uuid, message)
    if message is None:
        message = {}
    message = json.dumps({"type": "finish", "request_uuid": request_uuid, **message})
    loop.call_soon_threadsafe(asyncio.create_task, send_text(client_id, message))


# 对于静态数据的请求，使用文件资源管理器
if settings.host_web_ui:
    @app.get("/", response_class=RedirectResponse)
    async def root():
        return "/index.html"

    app.mount("/", StaticFiles(directory=settings.host_web_ui), name="static")
