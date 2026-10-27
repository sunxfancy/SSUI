from .project import search_project_root

__all__ = ["SSLoader", "VenvManager", "search_project_root"]


def __getattr__(name: str):
    """Load executor-heavy classes only when they are actually requested."""
    if name == "SSLoader":
        from .loader import SSLoader
        return SSLoader
    if name == "VenvManager":
        from .venv import VenvManager
        return VenvManager
    raise AttributeError(name)
