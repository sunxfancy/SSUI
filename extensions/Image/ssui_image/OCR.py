"""Image-to-text nodes with optional OCR runtimes."""

from functools import lru_cache
import os

import numpy as np

from ssui.base import Image
from ssui.config import SSUIConfig


def _pixels(image: Image) -> np.ndarray:
    if image._image is None:
        raise ValueError("OCR needs an input image")
    return np.asarray(image._image.convert("RGB"))


@lru_cache(maxsize=2)
def _rapidocr(size: str):
    try:
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import ModelType
    except ImportError as exc:
        raise RuntimeError("Install rapidocr and onnxruntime to use RapidOCR") from exc
    model_type = {"small": ModelType.SMALL, "medium": ModelType.MEDIUM}[size]
    return RapidOCR(params={"Det.model_type": model_type,
                            "Rec.model_type": model_type})


def RapidOCRText(config: SSUIConfig, image: Image) -> str:
    """Recognize text with PP-OCRv6 small ONNX models."""
    if config.is_prepare():
        return ""
    result = _rapidocr("small")(_pixels(image))
    return "\n".join(result.txts or [])


def RapidOCRMediumText(config: SSUIConfig, image: Image) -> str:
    """Recognize text with PP-OCRv6 medium ONNX models."""
    if config.is_prepare():
        return ""
    result = _rapidocr("medium")(_pixels(image))
    return "\n".join(result.txts or [])


@lru_cache(maxsize=4)
def _easyocr(languages: tuple[str, ...]):
    try:
        # python-bidi 0.4.x is the pure-Python build available on some ARM64 hosts.
        import bidi
        if not hasattr(bidi, "get_display"):
            from bidi.algorithm import get_display
            bidi.get_display = get_display
        import easyocr
    except ImportError as exc:
        raise RuntimeError("Install easyocr to use EasyOCR") from exc
    model_dir = os.environ.get("SSUI_OCR_MODEL_DIR")
    return easyocr.Reader(list(languages), gpu=False,
                          model_storage_directory=model_dir,
                          user_network_directory=model_dir)


def EasyOCRText(config: SSUIConfig, image: Image) -> str:
    """Recognize Chinese and English text with EasyOCR's CRAFT/CRNN pipeline."""
    if config.is_prepare():
        return ""
    return "\n".join(_easyocr(("ch_sim", "en")).readtext(_pixels(image), detail=0))
