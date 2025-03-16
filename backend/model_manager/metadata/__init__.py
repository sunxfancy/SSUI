"""
Initialization file for backend.model_manager.metadata

Usage:

from backend.model_manager.metadata import(
   AnyModelRepoMetadata,
   CommercialUsage,
   LicenseRestrictions,
   HuggingFaceMetadata,
)

from backend.model_manager.metadata.fetch import HuggingFaceMetadataFetch

data = HuggingFaceMetadataFetch().from_id("<REPO_ID>")
assert isinstance(data, HuggingFaceMetadata)
"""

from backend.model_manager.metadata.fetch import HuggingFaceMetadataFetch, ModelMetadataFetchBase
from backend.model_manager.metadata.metadata_base import (
    AnyModelRepoMetadata,
    AnyModelRepoMetadataValidator,
    BaseMetadata,
    HuggingFaceMetadata,
    ModelMetadataWithFiles,
    RemoteModelFile,
    UnknownMetadataException,
)

__all__ = [
    "AnyModelRepoMetadata",
    "AnyModelRepoMetadataValidator",
    "HuggingFaceMetadata",
    "HuggingFaceMetadataFetch",
    "ModelMetadataFetchBase",
    "BaseMetadata",
    "ModelMetadataWithFiles",
    "RemoteModelFile",
    "UnknownMetadataException",
]
