import os
import tempfile
import unittest

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestSD1Model(unittest.TestCase):
    def test_workflow(self):
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_image.SD1 import (
            SD1Clip,
            SD1Denoise,
            SD1Latent,
            SD1LatentDecode,
            SD1Model,
        )

        model = SD1Model.load(str(download_if_needed("sd1")))
        config = SSUIConfig()
        config.set_prepared(False)
        positive = Prompt("a beautiful girl, masterpiece, best quality")
        negative = Prompt("a bad image")

        positive, negative = SD1Clip(
            config("Prompt To Condition"), model, positive, negative
        )
        latent = SD1Latent(config("Create Empty Latent"))
        latent = SD1Denoise(config("Denoise"), model, latent, positive, negative)
        image = SD1LatentDecode(config("Latent to Image"), model, latent)

        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "result.png")
            image._image.save(output)
            self.assertTrue(os.path.exists(output))


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestSDXLModel(unittest.TestCase):
    def test_workflow(self):
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_image.SDXL import (
            SDXLClip,
            SDXLDenoise,
            SDXLLatent,
            SDXLLatentDecode,
            SDXLModel,
        )

        model = SDXLModel.load(str(download_if_needed("sdxl")))
        config = SSUIConfig()
        config.set_prepared(False)
        positive = Prompt("a beautiful girl in a red dress")
        negative = Prompt("a bad image")

        positive, negative = SDXLClip(
            config("Prompt To Condition"), model, positive, negative
        )
        latent = SDXLLatent(config("Create Empty Latent"))
        latent = SDXLDenoise(config("Denoise"), model, latent, positive, negative)
        image = SDXLLatentDecode(config("Latent to Image"), model, latent)

        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "result_sdxl.png")
            image._image.save(output)
            self.assertTrue(os.path.exists(output))


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestFluxModel(unittest.TestCase):
    def test_workflow(self):
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_image.Flux import (
            FluxClip,
            FluxDenoise,
            FluxLatent,
            FluxLatentDecode,
            FluxModel,
        )

        model = FluxModel.load(
            model_path=str(download_if_needed("flux", "transformer")),
            t5_encoder_path=str(download_if_needed("flux", "t5_encoder")),
            clip_path=str(download_if_needed("flux", "clip")),
            vae_path=str(download_if_needed("flux", "vae")),
        )
        config = SSUIConfig()
        config.set_prepared(False)
        positive = Prompt("a beautiful girl in a red dress")
        negative = Prompt("a bad image")

        positive, negative = FluxClip(
            config("Prompt To Condition"), model, positive, negative
        )
        latent = FluxLatent(config("Create Empty Latent"))
        latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
        image = FluxLatentDecode(config("Latent to Image"), model, latent)

        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "result_flux.png")
            image._image.save(output)
            self.assertTrue(os.path.exists(output))
