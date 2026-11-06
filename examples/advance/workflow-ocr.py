"""Image-to-text workflows. Install the chosen OCR runtime first (extensions/Image/OCR.md)."""

from ssui import Image, workflow
from ssui.config import SSUIConfig
from ssui_image.OCR import EasyOCRText, RapidOCRMediumText, RapidOCRText

config = SSUIConfig()


@workflow
def ocr_rapid(image: Image) -> str:
    return RapidOCRText(config("RapidOCR"), image)


@workflow
def ocr_rapid_medium(image: Image) -> str:
    return RapidOCRMediumText(config("RapidOCR Medium"), image)


@workflow
def ocr_easy(image: Image) -> str:
    return EasyOCRText(config("EasyOCR"), image)
