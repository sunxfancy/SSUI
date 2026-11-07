"""Real PP-OCRv6 smoke checks; opt in with SSUI_RUN_OCR_MODEL_TESTS=1."""

import os
from pathlib import Path
import unittest

from PIL import Image as PILImage, ImageDraw, ImageFont

from ssui.base import Image
from ssui.config import SSUIConfig
from tests.utils import add_extension_paths

add_extension_paths()
from ssui_image.OCR import EasyOCRText, RapidOCRMediumText, RapidOCRText


class OCRModelTest(unittest.TestCase):
    def test_prepare_does_not_load_weights(self):
        config = SSUIConfig()
        config.set_prepared()
        for node in (RapidOCRText, RapidOCRMediumText, EasyOCRText):
            with self.subTest(model=node.__name__):
                self.assertEqual(node(config, Image()), "")

    @unittest.skipUnless(os.environ.get("SSUI_RUN_OCR_MODEL_TESTS") == "1",
                         "Set SSUI_RUN_OCR_MODEL_TESTS=1 for real model inference")
    def test_small_and_medium_english_inference(self):
        fonts = (Path("C:/Windows/Fonts/arial.ttf"),
                 Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        font_path = next((p for p in fonts if p.is_file()), None)
        if font_path is None:
            self.skipTest("No suitable test font available")
        image = PILImage.new("RGB", (900, 180), "white")
        ImageDraw.Draw(image).text((25, 35), "SSUI OCR TEST 2026",
                                   font=ImageFont.truetype(str(font_path), 70),
                                   fill="black")
        for node in (RapidOCRText, RapidOCRMediumText):
            with self.subTest(model=node.__name__):
                output = node(SSUIConfig(), Image(image))
                self.assertIn("SSUIOCRTEST2026", "".join(output.split()))

    @unittest.skipUnless(os.environ.get("SSUI_RUN_OCR_MODEL_TESTS") == "1"
                         and os.environ.get("SSUI_OCR_MODEL_DIR"),
                         "Set SSUI_RUN_OCR_MODEL_TESTS=1 and SSUI_OCR_MODEL_DIR")
    def test_easyocr_chinese_inference(self):
        font_path = Path("C:/Windows/Fonts/msyh.ttc")
        if not font_path.is_file():
            self.skipTest("Chinese test font unavailable")
        image = PILImage.new("RGB", (980, 200), "white")
        ImageDraw.Draw(image).text((30, 35), "图像文字识别 2026",
                                   font=ImageFont.truetype(str(font_path), 70),
                                   fill="black")
        output = EasyOCRText(SSUIConfig(), Image(image))
        self.assertIn("图像文字识别2026", "".join(output.split()))


if __name__ == "__main__":
    unittest.main()
