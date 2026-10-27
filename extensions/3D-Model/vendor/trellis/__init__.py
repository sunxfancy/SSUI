"""Load optional CUDA renderers only when explicitly requested."""
import importlib
__all__ = ['models', 'modules', 'pipelines', 'renderers', 'representations', 'utils']
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    value = importlib.import_module(f'.{name}', __name__)
    globals()[name] = value
    return value
