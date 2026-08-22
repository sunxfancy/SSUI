import os
import yaml
from pydantic import BaseModel, Field

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
        self._allow_extension_packages()
        self.executor.load(path)

    def _allow_extension_packages(self):
        """动态放行扩展提供的 SDK 包与项目声明的 ssui_* 依赖。

        允许以下模块在沙盒中导入：
        - 扩展目录下的 ``ssui_*`` Python 包（如 ssui_image / ssui_video）
        - 各扩展 ``ssextension.yaml`` 中 ``server.packages`` 声明的包
        - 项目 ``ssproject.yaml`` dependencies 中以 ``ssui_`` 开头的包
        """
        if not hasattr(self.executor, "allow_modules"):
            return

        allowed = set()
        extensions_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "extensions")
        )
        if os.path.isdir(extensions_root):
            for entry in os.listdir(extensions_root):
                extension_dir = os.path.join(extensions_root, entry)
                if not os.path.isdir(extension_dir):
                    continue
                for sub in os.listdir(extension_dir):
                    sub_path = os.path.join(extension_dir, sub)
                    if (
                        sub.startswith("ssui_")
                        and os.path.isdir(sub_path)
                        and os.path.exists(os.path.join(sub_path, "__init__.py"))
                    ):
                        allowed.add(sub)
                yaml_path = os.path.join(extension_dir, "ssextension.yaml")
                if os.path.exists(yaml_path):
                    try:
                        with open(yaml_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        packages = ((data.get("server") or {}).get("packages")) or []
                        allowed.update(p for p in packages if isinstance(p, str))
                    except Exception:
                        continue

        project_root = search_project_root(os.path.dirname(self.current_file_path))
        if project_root is not None:
            try:
                project = SSProject(path=project_root)
                for dep in project.dependencies_map():
                    if dep.startswith("ssui_"):
                        allowed.add(dep)
            except Exception:
                pass

        if allowed:
            self.executor.allow_modules(list(allowed))

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
        if path == os.path.dirname(path):
            return None
