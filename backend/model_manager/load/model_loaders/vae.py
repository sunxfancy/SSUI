# Copyright (c) 2024, Lincoln D. Stein and the InvokeAI Development Team
"""Class for VAE model loading in """

from typing import Optional

from diffusers import AutoencoderKL

from backend.model_manager import (
    AnyModelConfig,
    BaseModelType,
    ModelFormat,
    ModelType,
)
from backend.model_manager.config import AnyModel, SubModelType, VAECheckpointConfig
from backend.model_manager.load.model_loader_registry import ModelLoaderRegistry
from backend.model_manager.load.model_loaders.generic_diffusers import GenericDiffusersLoader


@ModelLoaderRegistry.register(base=BaseModelType.Any, type=ModelType.VAE, format=ModelFormat.Diffusers)
@ModelLoaderRegistry.register(base=BaseModelType.Any, type=ModelType.VAE, format=ModelFormat.Checkpoint)
class VAELoader(GenericDiffusersLoader):
    """Class to load VAE models."""

    def _load_model(
        self,
        config: AnyModelConfig,
        submodel_type: Optional[SubModelType] = None,
    ) -> AnyModel:
        if isinstance(config, VAECheckpointConfig):
            return AutoencoderKL.from_single_file(
                config.path,
                torch_dtype=self._torch_dtype,
            )
        else:
            return super()._load_model(config, submodel_type)
