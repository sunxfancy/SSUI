import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image as PILImage

from ssui.base import Prompt
from ssui.config import SSUIConfig

from tests.fakes.sd import (
    FakeFluxModel,
    FakeSD1Model,
    FakeSDXLModel,
    fake_clip,
    fake_decode,
    fake_denoise,
    fake_latent,
)


class TestSD1Workflow(unittest.TestCase):
    """给定假模型输出，验证 SD1 工作流从 Clip 到 Decode 能跑通。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.config = SSUIConfig()
        self.positive = Prompt("a beautiful girl, masterpiece, best quality")
        self.negative = Prompt("a bad image")

    @patch("ssui_image.SD1.SD1Model", FakeSD1Model)
    @patch("ssui_image.SD1.SD1Clip", fake_clip)
    @patch("ssui_image.SD1.SD1Latent", fake_latent)
    @patch("ssui_image.SD1.SD1Denoise", fake_denoise)
    @patch("ssui_image.SD1.SD1LatentDecode", fake_decode)
    def test_workflow(self):
        from ssui_image.SD1 import (
            SD1Clip,
            SD1Denoise,
            SD1Latent,
            SD1LatentDecode,
            SD1Model,
        )

        model = SD1Model.load("fake/model/path")
        positive, negative = SD1Clip(
            self.config("Prompt To Condition"), model, self.positive, self.negative
        )
        latent = SD1Latent(self.config("Create Empty Latent"))
        latent = SD1Denoise(self.config("Denoise"), model, latent, positive, negative)
        image = SD1LatentDecode(self.config("Latent to Image"), model, latent)

        self.assertIsInstance(image._image, PILImage.Image)
        output = os.path.join(self.tmp_dir, "result_sd1.png")
        image._image.save(output)
        self.assertTrue(os.path.exists(output))


class TestSDXLWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.config = SSUIConfig()
        self.positive = Prompt("a beautiful girl in a red dress")
        self.negative = Prompt("a bad image")

    @patch("ssui_image.SDXL.SDXLModel", FakeSDXLModel)
    @patch("ssui_image.SDXL.SDXLClip", fake_clip)
    @patch("ssui_image.SDXL.SDXLLatent", fake_latent)
    @patch("ssui_image.SDXL.SDXLDenoise", fake_denoise)
    @patch("ssui_image.SDXL.SDXLLatentDecode", fake_decode)
    def test_workflow(self):
        from ssui_image.SDXL import (
            SDXLClip,
            SDXLDenoise,
            SDXLLatent,
            SDXLLatentDecode,
            SDXLModel,
        )

        model = SDXLModel.load("fake/model/path")
        positive, negative = SDXLClip(
            self.config("Prompt To Condition"), model, self.positive, self.negative
        )
        latent = SDXLLatent(self.config("Create Empty Latent"))
        latent = SDXLDenoise(self.config("Denoise"), model, latent, positive, negative)
        image = SDXLLatentDecode(self.config("Latent to Image"), model, latent)

        self.assertIsInstance(image._image, PILImage.Image)
        output = os.path.join(self.tmp_dir, "result_sdxl.png")
        image._image.save(output)
        self.assertTrue(os.path.exists(output))


class TestFluxWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.config = SSUIConfig()
        self.positive = Prompt("a beautiful girl in a red dress")
        self.negative = Prompt("a bad image")

    @patch("ssui_image.Flux.FluxModel", FakeFluxModel)
    @patch("ssui_image.Flux.FluxClip", fake_clip)
    @patch("ssui_image.Flux.FluxLatent", fake_latent)
    @patch("ssui_image.Flux.FluxDenoise", fake_denoise)
    @patch("ssui_image.Flux.FluxLatentDecode", fake_decode)
    def test_workflow(self):
        from ssui_image.Flux import (
            FluxClip,
            FluxDenoise,
            FluxLatent,
            FluxLatentDecode,
            FluxModel,
        )

        model = FluxModel.load(
            model_path="fake/flux.safetensors",
            t5_encoder_path="fake/t5",
            clip_path="fake/clip",
            vae_path="fake/vae.safetensors",
        )
        positive, negative = FluxClip(
            self.config("Prompt To Condition"), model, self.positive, self.negative
        )
        latent = FluxLatent(self.config("Create Empty Latent"))
        latent = FluxDenoise(self.config("Denoise"), model, latent, positive, negative)
        image = FluxLatentDecode(self.config("Latent to Image"), model, latent)

        self.assertIsInstance(image._image, PILImage.Image)
        output = os.path.join(self.tmp_dir, "result_flux.png")
        image._image.save(output)
        self.assertTrue(os.path.exists(output))
