from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from diffusers import UNet2DConditionModel

from backend.patches.layer_patcher import LayerPatcher
from backend.patches.model_patch_raw import ModelPatchRaw
from backend.stable_diffusion.extensions.base import ExtensionBase

if TYPE_CHECKING:
    from backend.util.original_weights_storage import OriginalWeightsStorage


class LoRAExt(ExtensionBase):
    def __init__(
        self,
        lora_model,
        weight: float,
    ):
        super().__init__()
        self._lora_model = lora_model
        self._weight = weight

    @contextmanager
    def patch_unet(self, unet: UNet2DConditionModel, original_weights: OriginalWeightsStorage):
        lora_model = self._lora_model.lora.model
        assert isinstance(lora_model, ModelPatchRaw)
        LayerPatcher.apply_smart_model_patch(
            model=unet,
            prefix="lora_unet_",
            patch=lora_model,
            patch_weight=self._weight,
            original_weights=original_weights,
            original_modules={},
            dtype=unet.dtype,
            force_direct_patching=True,
            force_sidecar_patching=False,
        )
        del lora_model

        yield
