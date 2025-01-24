import os
import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

class ExtensionManager:
    def __init__(self, path: str = None):
        self.modules = {}
        self.extensions = {}
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "..", "extensions")
            path = os.path.normpath(path)
        self.path = path

    def detectExtensions(self, app: FastAPI):
        for dir in os.listdir(self.path):
            yaml_path = os.path.join(self.path, dir, "ssextension.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "r") as f:
                    data = yaml.load(f, Loader=yaml.FullLoader)
                    data["path"] = os.path.join(self.path, dir)
                    if "name" not in data:
                        data["name"] = dir
                    if data["name"] not in self.extensions:
                        self.extensions[data["name"]] = data
                        
        self.loadPythonScripts(app)
        self.setFileAPIforExtension(app)
                    
    @staticmethod
    def instance():
        if not hasattr(ExtensionManager, "_instance"):
            ExtensionManager._instance = ExtensionManager()
        return ExtensionManager._instance
    
    def getExtensions(self, name: str):
        return self.extensions[name]
    
    def loadPythonScripts(self, app: FastAPI):
        for name, data in self.extensions.items():
            if "server" in data:
                if "main" in data["server"]:
                    script_path = os.path.join(data["path"], data["server"]["main"])
                    import importlib.util
                    try:
                        spec = importlib.util.spec_from_file_location(name, script_path)
                        module = importlib.util.module_from_spec(spec)
                        module.app = app
                        spec.loader.exec_module(module)
                        self.modules[name] = module
                    except Exception as e:
                        print(e)
                        self.modules[name] = None

    def setFileAPIforExtension(self, app: FastAPI):
        for name, data in self.extensions.items():
            if "web_ui" in data:
                if "dist" in data["web_ui"]:
                    dist_path = os.path.normpath(os.path.join(data["path"], data["web_ui"]["dist"]))
                    if os.path.exists(dist_path):
                        print(f"Setting static files for {name} at {dist_path}")
                        app.mount(f"/extension/{name}/dist", StaticFiles(directory=dist_path), name=name)