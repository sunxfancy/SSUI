import os
import torch
from typing import Dict, Any
from server.models import ScriptFunctionInfo
from ss_executor import SSLoader, search_project_root
from ss_executor.scheduler import TaskScheduler
from ss_executor.model import Task

class ScriptService:
    def __init__(self, scheduler: TaskScheduler):
        self.scheduler = scheduler
    
    def get_script_functions(self, script_path: str) -> Dict[str, Any]:
        try:
            script_path = os.path.normpath(script_path)
            if not os.path.exists(script_path):
                return {"error": "Script path not found"}
            
            project_root = search_project_root(os.path.dirname(script_path))
            if project_root is None:
                return {"error": "Project root not found"}
            
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
                func.__name__: ScriptFunctionInfo(
                    params={param: getTypeName(param_types[param]) for param in param_types},
                    returns=(
                        [getTypeName(t) for t in return_type.__args__]
                        if return_type.__name__ == "tuple" or return_type.__name__ == "Tuple"
                        else [getTypeName(return_type)]
                    ),
                )
                for func, param_types, return_type in loader.callables
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def prepare_script(self, script_path: str, callable: str) -> Dict[str, Any]:
        try:
            script_path = os.path.normpath(script_path)
            if not os.path.exists(script_path):
                return {"error": "Path not found"}
            
            return await self.scheduler.run_task(
                Task(script=script_path, callable=callable, is_prepare=True, use_sandbox=True)
            )
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_script(self, script_path: str, callable: str, params: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
        try:
            script_path = os.path.normpath(script_path)
            return await self.scheduler.run_task(
                Task(
                    script=script_path,
                    callable=callable,
                    params=params,
                    details=details,
                    is_prepare=False,
                    use_sandbox=True,
                )
            )
        except Exception as e:
            return {"error": str(e)}
    
    def get_torch_version(self) -> str:
        return torch.torch_version.__version__
    
    def get_device_info(self) -> str:
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        else:
            return "cpu" 