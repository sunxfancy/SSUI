from ssui.native_quantization import Int8Linear
from backend.model_manager.load.model_cache.torch_module_autocast.custom_modules.custom_linear import (
    autocast_linear_forward_sidecar_patches,
)
from backend.model_manager.load.model_cache.torch_module_autocast.custom_modules.custom_module_mixin import (
    CustomModuleMixin,
)


class CustomInt8Linear(Int8Linear, CustomModuleMixin):
    def _autocast_forward(self, input):
        return self.quantized_forward(input)

    def forward(self, input):
        if self._patches_and_weights:
            return autocast_linear_forward_sidecar_patches(self, input, self._patches_and_weights)
        return self.quantized_forward(input)
