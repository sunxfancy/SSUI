# SSUI Sandbox Module Documentation

## Overview

The SSUI Sandbox module is a secure execution environment for safely running restricted Python code, particularly for calling SSUI APIs. The module provides two execution modes: Sandbox mode (`Sandbox`) and No-Sandbox mode (`NoSandbox`).

## Core Components

### ModuleBundle

`ModuleBundle` is a data class used to encapsulate module execution results:

```python
@dataclass
class ModuleBundle:
    callables: List[Callable]  # List of callable objects
    config: SSUIConfig         # SSUI configuration
```

### ModuleExecutor

`ModuleExecutor` is an abstract base class that defines a unified interface for module executors:

- `execute_file(path: str) -> Optional[ModuleBundle]`: Execute file and return ModuleBundle
- `load(path: str) -> None`: Load module, prepare execution environment
- `execute_module() -> Optional[ModuleBundle]`: Execute loaded module and return ModuleBundle

## Sandbox Mode (Sandbox)

The `Sandbox` class provides a secure environment for executing restricted Python code.

### Key Features

1. **Module Whitelist**: By default, only allows importing system libraries like `ssui`, `ssui_image`... and the `typing` module
2. **Restricted Built-in Functions**: Uses `RestrictedPython` to provide secure built-in functions
3. **Safe Attribute Access**: Implemented through `_safe_getattr`, `_safe_getiter`, and `_safe_getitem` methods
4. **Safe Import Mechanism**: Controls which modules can be imported through the `_safe_import` method

### Main Methods

- `__init__()`: Initialize sandbox environment
- `_setup_restricted_globals()`: Set up restricted global environment
- `allow_module(module_name: str)`: Add module to the allowed import whitelist
- `allow_modules(module_names: List[str])`: Add multiple modules to the allowed import whitelist
- `load(path: str)`: Load module, prepare execution environment
- `execute_module() -> Optional[ModuleBundle]`: Execute loaded module and return ModuleBundle
- `set_api_function(name: str, func: Callable)`: Add or update secure API function

## No-Sandbox Mode (NoSandbox)

The `NoSandbox` class provides an unrestricted module execution environment, suitable for scenarios requiring full access to Python functionality.

### Main Methods

- `__init__()`: Initialize no-sandbox environment
- `load(path: str)`: Load module
- `execute_module() -> Optional[ModuleBundle]`: Execute loaded module and return ModuleBundle

## Usage Examples

### Sandbox Mode

```python
# Create sandbox environment
sandbox = Sandbox()

# Optional: Add allowed modules
sandbox.allow_module("numpy")

# Execute file
result = sandbox.execute_file("path/to/your/script.py")

# Use results
if result:
    callables = result.callables
    config = result.config
```

### No-Sandbox Mode

```python
# Create no-sandbox environment
no_sandbox = NoSandbox()

# Execute file
result = no_sandbox.execute_file("path/to/your/script.py")

# Use results
if result:
    callables = result.callables
    config = result.config
```

## Security Considerations

1. Sandbox mode provides basic security protection, but should still be used with caution
2. No-sandbox mode has no security restrictions and should only be used for trusted code
3. Carefully consider security implications when using `allow_module` and `allow_modules` methods
4. Exceptions in the sandbox environment will be caught and logged but won't interrupt execution

## Debugging

The Sandbox class provides debugging functionality that can be enabled by setting `debug = True`:

```python
sandbox = Sandbox()
sandbox.debug = True
```

When debugging is enabled, it will print the restricted-transformed source code, which helps in troubleshooting issues. 