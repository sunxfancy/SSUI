import os
import sys
import yaml
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from ss_executor.sandbox import Sandbox, NoSandbox

class SSLoader:
    def __init__(self, use_sandbox: bool = True):
        self.callables = []
        self.use_sandbox = use_sandbox
        self.executor = Sandbox() if use_sandbox else NoSandbox()
        self.config = None
        self.current_file_path = None

    def load(self, path: str):
        """加载模块"""
        self.current_file_path = os.path.abspath(path)
        self.executor.load(path)

    # 执行模块并获取可调用对象
    def Execute(self):
        """执行模块并获取可调用对象"""
        if not self.current_file_path:
            raise ValueError("No file path set. Call load() first.")
            
        module_bundle = self.executor.execute_module()
        
        if module_bundle:
            self.callables = module_bundle.callables
            self.config = module_bundle.config
        else:
            raise ValueError("Failed to execute module.")

    # 准备调用目标函数
    def GetConfig(self, name: str) -> dict | None:
        callable = None
        for func, param_types, return_type in self.callables:
            if func.__name__ == name:
                callable = func
                param_types = param_types
                return_type = return_type
                break
        
        if callable:
            self.config.set_prepared()
            params = {}
            for param in param_types:
                params[param] = None
            callable(**params)
            return self.config._config

    def Show(self):
        print(self.callables)
        for func, param_types, return_type in self.callables:
            param_type = {param: param_types[param].__module__ + '.' + param_types[param].__name__ for param in param_types}
            return_type = [return_type.__name__]
            print(f"API: {func.__name__}")
            print(f"Parameters: {param_type}")
            print(f"Return type: {return_type}")
            print()


class SSProject(BaseModel):
    path: str = Field(description="The path to the project")
    ssui_version: str = Field(description="The version of SSUI")
    dependencies: list[str] = Field(description="The dependencies of the project")

    def __init__(self, path: str):
        config = yaml.load(open(os.path.join(path, "ssproject.yaml"), "r"), Loader=yaml.FullLoader)
        super().__init__(path=path, ssui_version=config['ssui_version'], dependencies=config['dependencies'])
    
    def version(self) -> str:
        return self.ssui_version
    
    def dependencies_map(self) -> dict[str, str]:
        def parse_version(version_str: str) -> tuple[str, str]:
            parts = version_str.split(' = ')
            return parts[0], parts[1]
        
        deps_map = {}
        for dep in self.dependencies:
            name, version = parse_version(dep)
            deps_map[name] = version
            
        return deps_map

def search_project_root(path):
    while True:
        if os.path.exists(os.path.join(path, "ssproject.yaml")):
            return path
        path = os.path.dirname(path)
