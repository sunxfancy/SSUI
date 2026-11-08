"""Compatibility import for backend inference API."""
import sys
from backend.plugins.image.api import conditioning as _implementation
sys.modules[__name__] = _implementation
