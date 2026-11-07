"""Native ByteDance Lance backend. Loading defaults to NF4 weight quantization."""

__all__ = ["LancePipeline", "LanceOutput"]


def __getattr__(name):
    if name in __all__:
        from .pipeline import LanceOutput, LancePipeline

        return {"LancePipeline": LancePipeline, "LanceOutput": LanceOutput}[name]
    raise AttributeError(name)
