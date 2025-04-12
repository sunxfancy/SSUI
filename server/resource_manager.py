import os
from pathlib import Path

from backend.model_manager.config import AnyModelConfig
from backend.model_manager.probe import ModelProbe

class IReadOnlyResourceProvider:
    def __init__(self, namespace: str):
        self.namespace = namespace
    
    def getNamespace(self):
        return self.namespace    
    
    def getResource(self, url):
        pass

class IResourceProvider(IReadOnlyResourceProvider):
    def __init__(self, namespace: str):
        super().__init__(namespace)
        
    def setResource(self, url, data):
        pass

class ResourceManager:
    def __init__(self):
        self.resource_provider = []

    def registerProvider(self, provider: IResourceProvider):
        self.resource_provider.append(provider)

    def getResource(self, url):
        for provider in self.resource_provider:
            if url.startswith(provider.getNamespace()):
                return provider.getResource(url)
        return None

    def registerAPI(self, app, provider):
        @app.get(f"/res/{provider.getNamespace()}/")
        async def res_get(path: str):
            return provider.getResource(path)
        
        @app.post(f"/res/{provider.getNamespace()}/")
        async def res_set(path: str, data):
            return provider.setResource(path, data)

class FileResourceProvider(IResourceProvider):
    def __init__(self, root: str):
        super().__init__("file")
        self.root = root

    def getResource(self, url):
        path = url[len(self.namespace):]
        if path.startswith("/"):
            path = path[1:]
        path = os.path.join(self.root, path)
        if os.path.exists(path):
            return open(path, "rb").read()
        return None
    
    def setResource(self, url, data):
        path = url[len(self.namespace):]
        if path.startswith("/"):
            path = path[1:]
        path = os.path.join(self.root, path)
        with open(path, "wb") as f:
            f.write(data)
        return "OK"


class ModelInfoCache:
    def __init__(self):
        self.cache = {}

    def _get(self, model_path: str):
        if model_path in self.cache:
            return self.cache[model_path]
        else:
            try:
                model_config = ModelProbe.probe(Path(model_path))
                self.cache[model_path] = model_config
                return model_config
            except Exception as e:
                return None
    
    @classmethod
    def get(cls, model_path: str):
        return cls.instance()._get(model_path)

    def _set(self, model_path: str, model_config: AnyModelConfig):
        self.cache[model_path] = model_config
    
    @classmethod
    def set(cls, model_path: str, model_config: AnyModelConfig):
        cls.instance()._set(model_path, model_config)

    def _clear(self):
        self.cache.clear()

    @classmethod
    def clear(cls):
        cls.instance()._clear()

    @classmethod
    def instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance
