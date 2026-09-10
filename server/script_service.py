import ast
import os
import torch
from typing import Dict, Any
from server.models import FlowOperatorInfo, ScriptFunctionInfo
from ss_executor import SSLoader, search_project_root
from ss_executor.scheduler import TaskScheduler
from ss_executor.model import Task
from flow_compiler import compile_flow_file

class ScriptService:
    def __init__(self, scheduler: TaskScheduler):
        self.scheduler = scheduler
    
    def get_script_functions(self, script_path: str) -> Dict[str, Any]:
        try:
            script_path = self.resolve_script_path(script_path)
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
            script_path = self.resolve_script_path(script_path)
            if not os.path.exists(script_path):
                return {"error": "Path not found"}
            
            return await self.scheduler.run_task(
                Task(script=script_path, callable=callable, is_prepare=True, use_sandbox=True)
            )
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_script(self, script_path: str, callable: str, params: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
        try:
            script_path = self.resolve_script_path(script_path)
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

    def resolve_script_path(self, script_path: str) -> str:
        """Return an executable script path, compiling ``.flow`` on demand."""
        normalized = os.path.normpath(script_path)
        if normalized.lower().endswith(".flow"):
            return compile_flow_file(normalized)
        return normalized

    def compile_flow(self, flow_path: str) -> Dict[str, Any]:
        try:
            return {"success": True, "script_path": compile_flow_file(flow_path)}
        except Exception as e:
            return {"error": str(e)}

    def get_flow_operators(self, flow_path: str) -> Dict[str, Any]:
        """Describe typed project and extension callables without executing them."""
        directory = os.path.dirname(os.path.abspath(flow_path))
        if not os.path.isdir(directory):
            return {"error": "Flow directory not found"}
        operators: list[FlowOperatorInfo] = []
        errors: list[dict[str, str]] = []

        def return_types(annotation, fallback=None):
            if annotation is None:
                return [fallback] if fallback else []
            source = ast.unparse(annotation)
            if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value) in ("tuple", "Tuple"):
                value = annotation.slice
                return [ast.unparse(item) for item in value.elts] if isinstance(value, ast.Tuple) else [ast.unparse(value)]
            return [] if source in ("None", "NoneType") else [source]

        def add_callable(module, source_name, node, callable_name=None, fallback_return=None):
            args = [*node.args.posonlyargs, *node.args.args]
            public_args = [arg for arg in args if arg.arg not in ("self", "cls", "config")]
            if any(arg.annotation is None for arg in public_args):
                return
            name = callable_name or node.name
            operators.append(FlowOperatorInfo(
                module=module, name=name, callable=name,
                params={arg.arg: ast.unparse(arg.annotation) for arg in public_args},
                returns=return_types(node.returns, fallback_return), source=source_name,
            ))

        def inspect_file(path, module, source_name):
            try:
                with open(path, "r", encoding="utf-8") as source:
                    tree = ast.parse(source.read(), filename=source_name)
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                        add_callable(module, source_name, node)
                    elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                        for method in node.body:
                            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name == "load":
                                add_callable(module, source_name, method, f"{node.name}.load", node.name)
            except (OSError, UnicodeError, SyntaxError) as exc:
                errors.append({"source": source_name, "error": str(exc)})

        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename.endswith(".flow.py"):
                continue
            module = filename[:-3]
            if not module.isidentifier():
                errors.append({"source": filename, "error": "filename is not a valid Python module name"})
                continue
            inspect_file(os.path.join(directory, filename), module, filename)

        extensions_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "extensions"))
        if os.path.isdir(extensions_root):
            for extension in sorted(os.listdir(extensions_root)):
                extension_path = os.path.join(extensions_root, extension)
                if not os.path.isdir(extension_path):
                    continue
                for package in sorted(os.listdir(extension_path)):
                    package_path = os.path.join(extension_path, package)
                    if not package.startswith("ssui_") or not os.path.isdir(package_path):
                        continue
                    for filename in sorted(os.listdir(package_path)):
                        if filename.endswith(".py") and filename != "__init__.py":
                            module = f"{package}.{filename[:-3]}"
                            inspect_file(os.path.join(package_path, filename), module, f"{module}.py")
        return {"operators": operators, "errors": errors}
    
    def get_torch_version(self) -> str:
        return torch.torch_version.__version__
    
    def get_device_info(self) -> str:
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        else:
            return "cpu"
