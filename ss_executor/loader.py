import importlib
import importlib.util
from importlib.machinery import ModuleSpec, SourceFileLoader
import os
import sys
import yaml
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from ssui.annotation import get_callables, reset_callables

class SSLoader:
    def __init__(self):
        self.callables = []
        self.module : ModuleSpec = None
        self.spec : ModuleSpec = None

    def load(self, path: str):
        file_path = os.path.abspath(path)
        # Check if spec is None (e.g., file not found)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find module at: {file_path}")
        
        # Define the module name and file path
        module_name = file_path.split("/")[-1].split(".")[0]

        # Create a module specification
        self.spec = importlib.util.spec_from_file_location(module_name, file_path)

        # Create a module object from the specification
        self.module = importlib.util.module_from_spec(self.spec)

        # Get the module's loader and execute the module
        loader = SourceFileLoader(module_name, file_path)
        self.spec.loader = loader

    # Execute the module and get the callables
    def Execute(self):
        reset_callables()
        self.spec.loader.exec_module(self.module)
        self.callables = get_callables()
        if self.module.config:
            self.config = self.module.config

    # Prepare call the target function
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
            print(f"Config: {callable.__name__}")
            print(f"Parameters: {params}")
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
