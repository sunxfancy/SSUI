import os
from typing import Optional


def search_project_root(path: str) -> Optional[str]:
    """Find the nearest parent containing ``ssproject.yaml``."""
    path = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(path, "ssproject.yaml")):
            return path
        parent = os.path.dirname(path)
        if path == parent:
            return None
        path = parent
