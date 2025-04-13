from abc import ABC, abstractmethod

import ast
import builtins
from dataclasses import dataclass
import os
import importlib.util
from importlib.machinery import SourceFileLoader
from typing import Any, Dict, List, Literal, Optional, Callable, TYPE_CHECKING
from RestrictedPython import compile_restricted, safe_builtins, utility_builtins
from RestrictedPython.Guards import safer_getattr, guarded_unpack_sequence
from RestrictedPython.PrintCollector import PrintCollector
from RestrictedPython.transformer import RestrictingNodeTransformer

from ssui.annotation import get_callables, reset_callables
from ssui.config import SSUIConfig

if TYPE_CHECKING:
    from ss_executor.loader import ModuleExecutor

@dataclass
class ModuleBundle:
    callables: List[Callable]
    config: SSUIConfig

class ModuleExecutor(ABC):
    """模块执行器的抽象基类，提供统一的接口来获取ModuleBundle"""
    def execute_file(self, path: str) -> Optional[ModuleBundle]:
        """执行文件并返回ModuleBundle"""
        self.load(path)
        return self.execute_module()
    
    @abstractmethod
    def load(self, path: str) -> None:
        """加载模块，准备执行环境"""
        pass
    
    @abstractmethod
    def execute_module(self) -> Optional[ModuleBundle]:
        """执行已加载的模块并返回ModuleBundle"""
        pass

class Sandbox(ModuleExecutor):
    """
    安全沙盒环境，用于执行受限制的Python代码，安全调用SSUI API。
    """
    debug = False

    def __init__(self):
        """
        初始化沙盒环境

        Args:
            ssui_api: 包含允许调用的SSUI API函数的字典
        """
        self.allowed_modules = set(['ssui', 'ssui_image', 'typing'])  # 初始化允许导入的模块集合
        self._setup_restricted_globals()
        self.module_path = None
        self.module_name = None
        self.compiled_code = None
        self.global_vars = None

    def _setup_restricted_globals(self):
        """设置受限制的全局环境"""
        self.my_collector = PrintCollector(getattr)
        # 基础安全内置函数

        builtins_dict = safe_builtins.copy()
        builtins_dict["_getattr_"] = self._safe_getattr
        self.restricted_globals = {
            "__builtins__": {
                **builtins_dict,
                **utility_builtins,
                "_print_": lambda *args: self.my_collector,
                "_unpack_sequence_": guarded_unpack_sequence,
                "_getitem_": self._safe_getitem,
                "_getiter_": self._safe_getiter,
                # 允许的基本内置函数
                "sum": builtins.sum,
                "min": builtins.min,
                "max": builtins.max,
                "abs": builtins.abs,
                "round": builtins.round,
                "len": builtins.len,
                # 添加导入功能
                "__import__": self._safe_import,
            }
        }

    def _safe_getattr(self, obj, name):
        """安全的获取属性"""
        print('getattr', obj, name)

        return getattr(obj, name)
    
    def _safe_getiter(self, obj):
        """安全的获取迭代器"""
        return iter(obj)

    def _safe_getitem(self, obj, key):
        """安全的获取item"""
        # TODO: 了解一下为何这个函数没有被实现
        return obj[key]
    
    def _safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """
        安全的导入函数，只允许导入白名单中的包
        
        Args:
            name: 要导入的模块名
            globals: 全局变量字典
            locals: 局部变量字典
            fromlist: 从模块中导入的名称列表
            level: 相对导入的级别
            
        Returns:
            导入的模块对象
        """

        first_part = name.split('.')[0]
        # 检查是否在白名单中
        if first_part not in self.allowed_modules:
            raise ImportError(f"导入被拒绝: 模块 '{name}' 不在允许列表中")
        
        print('imported', name)
        # 使用标准导入
        if fromlist:
            module = importlib.import_module(name)
            for item in fromlist:
                self.global_vars[item] = getattr(module, item)
        else:
            module = importlib.import_module(first_part)
            self.global_vars[name] = module
        
        return importlib.import_module(name)
        
    def allow_module(self, module_name: str) -> None:
        """
        将模块添加到允许导入的白名单中
        
        Args:
            module_name: 要允许导入的模块名称
        """
        self.allowed_modules.add(module_name)
        
    def allow_modules(self, module_names: List[str]) -> None:
        """
        将多个模块添加到允许导入的白名单中
        
        Args:
            module_names: 要允许导入的模块名称列表
        """
        for module_name in module_names:
            self.allowed_modules.add(module_name)
    
    def load(self, path: str) -> None:
        """
        加载模块，准备执行环境
        
        Args:
            path: 文件路径
        """
        self.module_path = os.path.abspath(path)
        self.module_name = os.path.basename(path).split(".")[0]
        
        # 读取文件内容
        with open(self.module_path, "r") as file:
            code = file.read()
            
        # 编译代码，允许注解
        self.compiled_code = compile_restricted(code, filename=self.module_name, mode="exec", flags=0)
        if self.debug:
            parsed_ast = ast.parse(code)
            restricted_ast = RestrictingNodeTransformer().visit(parsed_ast)
            ast.fix_missing_locations(restricted_ast)
            new_source = ast.unparse(restricted_ast)
            print('new_source:\n', new_source)

    def execute_module(self) -> Optional[ModuleBundle]:
        """
        执行已加载的模块并返回ModuleBundle
        
        Returns:
            ModuleBundle对象，包含执行结果
        """
        if not self.compiled_code:
            raise ValueError("No module loaded. Call load() first.")
            
        try:
            # 准备执行环境
            self.global_vars = self.restricted_globals.copy()

            # 执行代码
            reset_callables()
            exec(self.compiled_code, self.global_vars)
            return ModuleBundle(
                callables=get_callables(),
                config=self.global_vars.get("config")
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'exception in the code {e}')
            return None

    def set_api_function(self, name: str, func: Callable) -> None:
        """
        添加或更新安全API函数

        Args:
            name: API函数名
            func: API函数
        """
        # TODO: 需要实现，方便插件添加新功能
        pass

class NoSandbox(ModuleExecutor):
    """不使用沙盒环境的模块执行器"""
    
    def __init__(self):
        self.module = None
        self.spec = None
    
    def load(self, path: str) -> None:
        """加载模块"""
        file_path = os.path.abspath(path)
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find module at: {file_path}")
        
        # 定义模块名称和文件路径
        module_name = file_path.split("/")[-1].split(".")[0]

        # 创建模块规范
        self.spec = importlib.util.spec_from_file_location(module_name, file_path)

        # 从规范创建模块对象
        self.module = importlib.util.module_from_spec(self.spec)

        # 获取模块的加载器
        loader = SourceFileLoader(module_name, file_path)
        self.spec.loader = loader
    
    def execute_module(self) -> Optional[ModuleBundle]:
        """执行已加载的模块并返回ModuleBundle"""
        if not self.module or not self.spec:
            raise ValueError("No module loaded. Call load() first.")
            
        try:
            reset_callables()
            self.spec.loader.exec_module(self.module)
            
            return ModuleBundle(
                callables=get_callables(),
                config=getattr(self.module, "config", None)
            )
        except Exception as e:
            return None