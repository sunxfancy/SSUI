import builtins
from typing import Any, Dict, Optional, Callable
from RestrictedPython import compile_restricted, safe_builtins, utility_builtins
from RestrictedPython.Guards import safer_getattr, guarded_unpack_sequence
from RestrictedPython.PrintCollector import PrintCollector

class Sandbox:
    """
    安全沙盒环境，用于执行受限制的Python代码，安全调用SSUI API。
    """
    
    def __init__(self, ssui_api: Optional[Dict[str, Callable]] = None):
        """
        初始化沙盒环境
        
        Args:
            ssui_api: 包含允许调用的SSUI API函数的字典
        """
        self.ssui_api = ssui_api or {}
        self._setup_restricted_globals()
    
    def _setup_restricted_globals(self):
        """设置受限制的全局环境"""
        # 基础安全内置函数
        self.restricted_globals = {
            '__builtins__': {
                **safe_builtins,
                **utility_builtins,
                '_print_': PrintCollector,
                '_getattr_': safer_getattr,
                '_unpack_sequence_': guarded_unpack_sequence,
                # 允许的基本内置函数
                'sum': builtins.sum,
                'min': builtins.min,
                'max': builtins.max,
                'abs': builtins.abs,
                'round': builtins.round,
                'len': builtins.len,
            },
            # 提供安全的SSUI API访问
            'ssui': self.ssui_api
        }
    
    def execute(self, code: str) -> Dict[str, Any]:
        """
        在沙盒环境中执行代码
        
        Args:
            code: 要执行的Python代码字符串
        
        Returns:
            包含执行结果、输出和错误信息的字典
        """
        result = {
            'success': False,
            'result': None,
            'output': '',
            'error': None
        }
        
        try:
            # 编译受限代码
            byte_code = compile_restricted(code, filename='<inline>', mode='exec')
            
            # 准备执行环境
            local_vars = {}
            global_vars = self.restricted_globals.copy()
            
            # 执行代码
            exec(byte_code, global_vars, local_vars)
            
            # 收集打印输出
            if '_print' in local_vars and hasattr(local_vars['_print'], 'get'):
                result['output'] = local_vars['_print'].get()
            
            # 获取返回值(如果存在)
            if 'result' in local_vars:
                result['result'] = local_vars['result']
            
            result['success'] = True
        except Exception as e:
            result['error'] = f"{type(e).__name__}: {str(e)}"
        
        return result
    
    def set_api_function(self, name: str, func: Callable) -> None:
        """
        添加或更新安全API函数
        
        Args:
            name: API函数名
            func: API函数
        """
        self.ssui_api[name] = func
        self._setup_restricted_globals()  # 更新全局环境
