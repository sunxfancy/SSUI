# SSUI 沙盒模块文档

## 概述

SSUI 沙盒模块是一个安全执行环境，用于安全地运行受限制的 Python 代码，特别是用于调用 SSUI API。该模块提供了两种执行模式：沙盒模式（`Sandbox`）和无沙盒模式（`NoSandbox`）。

## 核心组件

### ModuleBundle

`ModuleBundle` 是一个数据类，用于封装模块执行的结果：

```python
@dataclass
class ModuleBundle:
    callables: List[Callable]  # 可调用对象列表
    config: SSUIConfig         # SSUI 配置
```

### ModuleExecutor

`ModuleExecutor` 是一个抽象基类，定义了模块执行器的统一接口：

- `execute_file(path: str) -> Optional[ModuleBundle]`: 执行文件并返回 ModuleBundle
- `load(path: str) -> None`: 加载模块，准备执行环境
- `execute_module() -> Optional[ModuleBundle]`: 执行已加载的模块并返回 ModuleBundle

## 沙盒模式 (Sandbox)

`Sandbox` 类提供了一个安全的环境来执行受限制的 Python 代码。

### 主要特性

1. **模块白名单**：默认只允许导入 `ssui`、`ssui_image`...等系统库 和 `typing` 模块
2. **受限内置函数**：使用 `RestrictedPython` 提供安全的内置函数
3. **安全属性访问**：通过 `_safe_getattr`、`_safe_getiter` 和 `_safe_getitem` 方法实现
4. **安全导入机制**：通过 `_safe_import` 方法控制哪些模块可以导入

### 主要方法

- `__init__()`: 初始化沙盒环境
- `_setup_restricted_globals()`: 设置受限制的全局环境
- `allow_module(module_name: str)`: 将模块添加到允许导入的白名单中
- `allow_modules(module_names: List[str])`: 将多个模块添加到允许导入的白名单中
- `load(path: str)`: 加载模块，准备执行环境
- `execute_module() -> Optional[ModuleBundle]`: 执行已加载的模块并返回 ModuleBundle
- `set_api_function(name: str, func: Callable)`: 添加或更新安全 API 函数

## 无沙盒模式 (NoSandbox)

`NoSandbox` 类提供了一个不限制的模块执行环境，适用于需要完全访问 Python 功能的场景。

### 主要方法

- `__init__()`: 初始化无沙盒环境
- `load(path: str)`: 加载模块
- `execute_module() -> Optional[ModuleBundle]`: 执行已加载的模块并返回 ModuleBundle

## 使用示例

### 沙盒模式

```python
# 创建沙盒环境
sandbox = Sandbox()

# 可选：添加允许导入的模块
sandbox.allow_module("numpy")

# 执行文件
result = sandbox.execute_file("path/to/your/script.py")

# 使用结果
if result:
    callables = result.callables
    config = result.config
```

### 无沙盒模式

```python
# 创建无沙盒环境
no_sandbox = NoSandbox()

# 执行文件
result = no_sandbox.execute_file("path/to/your/script.py")

# 使用结果
if result:
    callables = result.callables
    config = result.config
```

## 安全注意事项

1. 沙盒模式提供了基本的安全保护，但仍需谨慎使用
2. 无沙盒模式没有安全限制，应仅用于可信代码
3. 使用 `allow_module` 和 `allow_modules` 方法时应仔细考虑安全影响
4. 沙盒环境中的异常会被捕获并记录，但不会中断执行

## 调试

沙盒类提供了调试功能，可以通过设置 `debug = True` 来启用：

```python
sandbox = Sandbox()
sandbox.debug = True
```

启用调试后，将打印出经过限制转换后的源代码，有助于排查问题。
