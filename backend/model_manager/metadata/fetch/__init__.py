"""
Initialization file for backend.model_manager.metadata.fetch

Usage:
from backend.model_manager.metadata.fetch import (
    HuggingFaceMetadataFetch,
)

data = HuggingFaceMetadataFetch().from_id("<repo_id>")
assert isinstance(data, HuggingFaceMetadata)
"""

from backend.model_manager.metadata.fetch.fetch_base import ModelMetadataFetchBase
from backend.model_manager.metadata.fetch.huggingface import HuggingFaceMetadataFetch

__all__ = ["ModelMetadataFetchBase", "HuggingFaceMetadataFetch"]
