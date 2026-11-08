"""Lazy SDK exports; importing one capability does not load every model."""
from importlib import import_module

_EXPORTS = {'getModelLoader': ('SD1', 'getModelLoader'), 'SD1Model': ('SD1', 'SD1Model'), 'SD1Condition': ('SD1', 'SD1Condition'), 'SD1Clip': ('SD1', 'SD1Clip'), 'SD1Latent': ('SD1', 'SD1Latent'), 'SD1Lora': ('SD1', 'SD1Lora'), 'SD1Denoise': ('SD1', 'SD1Denoise'), 'SD1LatentDecode': ('SD1', 'SD1LatentDecode'), 'SD1IPAdapter': ('SD1', 'SD1IPAdapter'), 'SDXLModel': ('SDXL', 'SDXLModel'), 'SDXLCondition': ('SDXL', 'SDXLCondition'), 'SDXLClip': ('SDXL', 'SDXLClip'), 'SDXLLatent': ('SDXL', 'SDXLLatent'), 'SDXLLora': ('SDXL', 'SDXLLora'), 'SDXLDenoise': ('SDXL', 'SDXLDenoise'), 'SDXLLatentDecode': ('SDXL', 'SDXLLatentDecode'), 'AgentPaintAsset': ('PixelArt', 'AgentPaintAsset'), 'PixelSrcAsset': ('PixelArt', 'PixelSrcAsset'), 'RenderAgentPaint': ('PixelArt', 'RenderAgentPaint'), 'RenderPixelSrc': ('PixelArt', 'RenderPixelSrc'), 'FinalizePixelArt': ('PixelArt', 'FinalizePixelArt'), 'finalize_pixel_art_image': ('PixelArt', 'finalize_pixel_art_image')}
__all__ = list(_EXPORTS)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, symbol = _EXPORTS[name]
    value = getattr(import_module("." + module, __name__), symbol)
    globals()[name] = value
    return value
