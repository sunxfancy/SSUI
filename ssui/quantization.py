"""Workflow controls for model-load options (no torch dependency during prepare)."""

from .annotation import param
from .controller import Select


@param("quantization", Select("none", "fp8"), default="none")
def FP8Quantization(config):
    """Select FP8 weight storage for Wan/Hunyuan before loading the model."""
    return "none" if config.is_prepare() else config["quantization"]


@param("quantization", Select("none", "int8"), default="none")
def Int8Quantization(config):
    """Select optional TorchAO INT8 weight-only quantization before loading."""
    return "none" if config.is_prepare() else config["quantization"]
