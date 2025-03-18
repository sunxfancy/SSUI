import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import torch
import torch.torch_version
import sys
import os
import json
from server.resource_manager import FileResourceProvider, ResourceManager
import ssui
from ssui.base import Image

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from ss_executor import SSLoader, search_project_root

from .extensions import ExtensionManager

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    host_web_ui: str = "../web_ui/dist"

settings = Settings()
app = FastAPI()

ExtensionManager.instance().detectExtensions(app)

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")


if settings.host_web_ui:

    @app.get("/", response_class=RedirectResponse)
    async def root():
        return "/index.html"

    app.mount("/", StaticFiles(directory=settings.host_web_ui), name="static")
