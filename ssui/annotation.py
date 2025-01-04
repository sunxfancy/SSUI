import functools
import inspect

callables = []

# 用于记录 API 的装饰器
def workflow(func):
    signature = inspect.signature(func)
    param_types = {
        param.name: param.annotation
        for param in signature.parameters.values()
    }
    # 获取返回类型
    return_type = signature.return_annotation

    # 将 API 添加到 callables 列表
    callables.append((func, param_types, return_type))

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 在调用 API 时记录信息
        print(f"API called: {func.__name__}")
        # 记录参数
        print(f"Arguments: {args}, {kwargs}")
        # 调用原始 API
        result = func(*args, **kwargs)
        # 记录返回结果
        print(f"Return value: {result}")
        return result
    return wrapper

def reset_callables():
    callables.clear()

def get_callables():
    return callables