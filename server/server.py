from fastapi import FastAPI, WebSocket
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import torch
import torch.torch_version
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from ss_executor import SSLoader

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host_web_ui: str = "../web_ui/dist"


settings = Settings()
app = FastAPI()


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


def search_project_root(path):
    while True:
        if os.path.exists(os.path.join(path, "ssproject.yaml")):
            return path
        path = os.path.dirname(path)


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
async def prepare(script_path: str, callable: str, params: dict):
    script_path = os.path.normpath(script_path)
    project_root = search_project_root(os.path.dirname(script_path))
    
    loader = SSLoader()
    loader.load(script_path)
    loader.Execute()
    return loader.GetConfig(callable, params)
    
    

@app.post("/api/execute")
async def execute(script_path: str, callable: str, params: dict):
    script_path = os.path.normpath(script_path)
    project_root = search_project_root(os.path.dirname(script_path))
    # TODO: Check dependencies

    loader = SSLoader()
    loader.load(script_path)
    loader.Execute()

    for func, param_types, return_type in loader.callables:
        if func.__name__ == callable:
            # TODO：Convert the parameters to the correct type
            return func(**params)


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
