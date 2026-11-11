"""Load training utilities only when requested, keeping audio inference light."""
from importlib import import_module

_EXPORTS = {
    "instantiate_callbacks": "instantiators",
    "instantiate_loggers": "instantiators",
    "log_hyperparameters": "logging_utils",
    "get_pylogger": "pylogger",
    "enforce_tags": "rich_utils",
    "print_config_tree": "rich_utils",
    "extras": "utils",
    "get_metric_value": "utils",
    "task_wrapper": "utils",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
