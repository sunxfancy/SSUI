import datetime
import threading
from typing import Optional
import uuid
import aioshutil
from fastapi import Body, FastAPI, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import torch
import torch.torch_version
import sys
import os
import json
from backend.model_manager.config import ModelType
from backend.model_manager.probe import ModelProbe
from ssui.base import Image
from pydantic_settings import BaseSettings
from contextlib import asynccontextmanager
import asyncio
from .resource_manager import ModelInfoCache

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from ss_executor import SSLoader, search_project_root
from .extensions import ExtensionManager


resources_dir: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources"))
settings_path: str = os.path.join(resources_dir, "ssui_config.json")

class ModelInfo(BaseModel):
    path: str
    name: str
    description: str
    base_model: str
    tags: list[str]


class Settings(BaseSettings):
    host_web_ui: str = os.path.join(os.path.dirname(__file__), "..", "frontend", "functional_ui", "dist")
    additional_model_dirs: list[str] = []
    installed_models: list[ModelInfo] = []

settings = Settings() if not os.path.exists(settings_path) else Settings.model_validate_json(open(settings_path, "r").read())

# 这是一个全局websocket的连接用户表
ws_clients = {}
loop = asyncio.get_event_loop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 检测扩展
    ExtensionManager.instance().detectExtensions(app)
    yield
    print("lifespan end")
    # 关闭所有连接
    for name,connection in ws_clients.items():
        await connection.close()

app = FastAPI(lifespan=lifespan)

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
            for filename in filenames:
                if filename.endswith(".safetensors") or filename.endswith(".pt") or filename.endswith(".ckpt"):
                    model_path = os.path.join(dirpath, filename)
                    # 检查模型是否已经安装，如果已安装则跳过
                    if any(model.path == model_path for model in settings.installed_models):
                        print(f"跳过已安装的模型: {model_path}")
                        continue
                    try:
                        model_config = ModelInfoCache.get(model_path)
                        scaned_models.append({ "path": model_path, "name": filename })
                        send_message(client_id, request_uuid, { "find_model": { "path": model_path, "name": filename } })
                    except Exception as e:
                        continue
    send_finish(client_id, request_uuid, { "models": scaned_models })


class ScanModelsRequest(BaseModel):
    scan_dir: str = Field(description="The directory to scan for models")


@app.post("/config/scan_models/{client_id}")
async def scan_models(client_id: str, request: ScanModelsRequest):
    scan_dir = os.path.normpath(request.scan_dir)
    print("scan_models", client_id, scan_dir)
    if not os.path.exists(scan_dir):
        return {"error": "Scan directory not found"}
    request_uuid = str(uuid.uuid4())
    threading.Thread(target=scan_target_dir, args=(scan_dir, client_id, request_uuid), daemon=True).start()
    return {"type": "start", "request_uuid": request_uuid, "message": "Models scan started", "callbacks": ["find_model"]}

@app.post("/config/install_model")
async def install_model(model_path: str = Body(..., embed=True), create_softlink: bool = Body(False, embed=True)):
    model_path = os.path.normpath(model_path)
    if not os.path.exists(model_path):
            return {"error": "Model path not found"}
    
    model_config = ModelInfoCache.get(model_path)
    if model_config is None:
        return {"error": "Model can not be loaded"}
    tags = []
    tags.append(model_config.base)
    if model_config.type == ModelType.LoRA:
        tags.append('lora')
    elif model_config.type == ModelType.T5Encoder:
        tags.append('t5')
    elif model_config.type == ModelType.VAE:
        tags.append('vae')

    if create_softlink:
        # 创建软链接
        settings.installed_models.append(ModelInfo(
            path=model_path, name=model_config.name, description=model_config.description, base_model=model_config.base, tags=tags))
    else:
        # 复制文件
        new_model_path = os.path.join(resources_dir, model_config.name)
        await aioshutil.copy(model_path, new_model_path)
        ModelInfoCache.set(model_path, model_config)
        settings.installed_models.append(ModelInfo(
            path=new_model_path, name=model_config.name, description=model_config.description, base_model=model_config.base, tags=tags))

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
    data['path'] = model_path
    return data

@app.get("/api/available_models")
async def available_models():
    return settings.installed_models


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
    
    loader = SSLoader()
    loader.load(script_path)
    loader.Execute()
    return loader.GetConfig(callable)

@app.post("/api/execute")
async def execute(script_path: str, callable: str, params: dict, details: dict):
    script_path = os.path.normpath(script_path)
    project_root = search_project_root(os.path.dirname(script_path))
    # TODO: Check dependencies

    loader = SSLoader()
    loader.load(script_path)
    loader.Execute()

    def convert_param(param: dict): 
        name = param['function']
        params = param['params']

        # 动态导入并获取属性,支持任意层级的包/模块/类/函数访问
        parts = name.split('.')
        current = __import__(parts[0])
        for part in parts[1:]:
            current = getattr(current, part)
        return current(**params)

    def find_callable(loader, callable):
        for func, param_types, return_type in loader.callables:
            if func.__name__ == callable:
                return func, param_types, return_type
        
    func, param_types, return_type = find_callable(loader, callable)

    print(script_path, callable, params, details)
    new_params = {}
    for name, param in params.items():
        print(name, param)
        new_params[name] = convert_param(param)

    # 注入配置
    loader.config._update = details

    result = func(**new_params)

    def convert_return(result):
        if isinstance(result, tuple):
            return [convert_return(r) for r in result]
        
        if isinstance(result, Image):
            current_time = datetime.datetime.now()
            output_dir = os.path.join(project_root, "output")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            path = os.path.join(output_dir, "image_" + current_time.strftime("%Y%m%d%H%M%S") + ".png")
            result._image.save(path)
            return {"type": "image", "path": path}

        return result

    # 确保返回一个数组
    if not isinstance(result, tuple):
        result = (result,)

    return convert_return(result)

@app.get("/file")
async def file(path: str):
    print("access file: ", path)
    if os.path.exists(path):
        if path.endswith(".png"):
            return FileResponse(path, media_type='image/png')
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            return FileResponse(path, media_type='image/jpeg')
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
        while True:
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

def send_finish(client_id: str, request_uuid: str, message: Optional[dict[str, any]] = None):
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
