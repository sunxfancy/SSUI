import datetime
from pathlib import Path
import signal
import threading
from typing import Optional
import uuid
from fastapi import Body, FastAPI, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import torch
import torch.torch_version
import sys
import os
import json
from backend.model_manager.probe import ModelProbe
from ssui.base import Image
from pydantic_settings import BaseSettings
from contextlib import asynccontextmanager
import asyncio
from asyncio import Queue

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from ss_executor import SSLoader, search_project_root
from .extensions import ExtensionManager

class Settings(BaseSettings):
    host_web_ui: str = os.path.join(os.path.dirname(__file__), "..", "frontend", "functional_ui", "dist")
    resources_dir: str = os.path.join(os.path.dirname(__file__), "..", "resources")
    additional_model_dirs: list[str] = []


settings = Settings()

# 这是一个全局websocket的连接用户表
ws_clients = {}
message_queue = Queue()
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
                    try:
                        model_config = ModelProbe.probe(Path(model_path))
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
async def install_model(model_path: str):
    model_path = os.path.normpath(model_path)
    if not os.path.exists(model_path):
            return {"error": "Model path not found"}
    # TODO 创建一个模型对象，并保存详细参数
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
async def available_models(category: str):
    pass

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
async def execute(script_path: str, callable: str, params: dict):
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

    print(script_path, callable, params)
    new_params = {}
    for name, param in params['params'].items():
        print(name, param)
        new_params[name] = convert_param(param)

    # 注入配置
    # loader.config._config = config

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
        extension_dir[name] = "/extension/" + name + "/dist/" + data['web_ui']['main']
    return extension_dir


@app.websocket("/")
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
