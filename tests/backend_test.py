import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from PIL import Image as PILImage

from tests.fakes.sd import FakeCondition


class TestBackendApi(unittest.TestCase):
    """给定假模型输出，验证 backend API 层（load/condition/denoise/decode）能跑通。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    @patch("ssui_image.api.model.load_model", lambda **kwargs: (object(), object(), object()))
    @patch(
        "ssui_image.api.conditioning.create_conditioning",
        lambda *args, **kwargs: FakeCondition(),
    )
    @patch(
        "ssui_image.api.denoise.denoise_image",
        lambda *args, **kwargs: torch.zeros(1, 4, 8, 8),
    )
    @patch(
        "ssui_image.api.denoise.decode_latents",
        lambda *args, **kwargs: PILImage.new("RGB", (64, 64), (10, 20, 30)),
    )
    def test_sd1_pipeline(self):
        from ssui_image.api.conditioning import create_conditioning
        from ssui_image.api.denoise import decode_latents, denoise_image
        from ssui_image.api.model import load_model

        unet, clip, vae = load_model(
            model_loader_service=object(), model_path=Path("fake")
        )
        positive_conditioning = create_conditioning("positive", clip)
        negative_conditioning = create_conditioning("negative", clip)
        latents = denoise_image(
            unet,
            positive_conditioning,
            negative_conditioning,
            seed=123454321,
            width=64,
            height=64,
            scheduler_name="ddim",
            cfg_scale=7.5,
            steps=3,
        )
        image = decode_latents(vae, latents)

        output = os.path.join(self.tmp_dir, "result.png")
        image.save(output)
        self.assertTrue(os.path.exists(output))

    @patch("ssui_image.api.model.load_sdxl_model", lambda **kwargs: (object(), object(), object(), object()))
    @patch(
        "ssui_image.api.conditioning.create_sdxl_conditioning",
        lambda *args, **kwargs: FakeCondition(),
    )
    @patch(
        "ssui_image.api.denoise.denoise_image",
        lambda *args, **kwargs: torch.zeros(1, 4, 8, 8),
    )
    @patch(
        "ssui_image.api.denoise.decode_latents",
        lambda *args, **kwargs: PILImage.new("RGB", (64, 64), (10, 20, 30)),
    )
    def test_sdxl_pipeline(self):
        from ssui_image.api.conditioning import create_sdxl_conditioning
        from ssui_image.api.denoise import decode_latents, denoise_image
        from ssui_image.api.model import load_sdxl_model

        unet, clip, clip2, vae = load_sdxl_model(object(), Path("fake"))
        positive = create_sdxl_conditioning(
            "positive", "", clip, clip2, 64, 64, 0, 0, 64, 64
        )
        negative = create_sdxl_conditioning(
            "negative", "", clip, clip2, 64, 64, 0, 0, 64, 64
        )
        latents = denoise_image(
            unet,
            positive,
            negative,
            seed=987654321,
            width=64,
            height=64,
            scheduler_name="dpmpp_2m_sde_k",
            cfg_scale=6,
            steps=3,
        )
        image = decode_latents(vae, latents)

        output = os.path.join(self.tmp_dir, "result_sdxl.png")
        image.save(output)
        self.assertTrue(os.path.exists(output))

    @patch("ssui_image.api.model.load_flux_model", lambda **kwargs: (object(), object(), object(), object()))
    @patch(
        "ssui_image.api.conditioning.create_flux_conditioning",
        lambda *args, **kwargs: FakeCondition(),
    )
    @patch(
        "ssui_image.api.denoise.flux_denoise_image",
        lambda *args, **kwargs: torch.zeros(1, 4, 8, 8),
    )
    @patch(
        "ssui_image.api.denoise.flux_decode_latents",
        lambda *args, **kwargs: PILImage.new("RGB", (64, 64), (10, 20, 30)),
    )
    def test_flux_pipeline(self):
        from ssui_image.api.conditioning import create_flux_conditioning
        from ssui_image.api.denoise import flux_decode_latents, flux_denoise_image
        from ssui_image.api.model import load_flux_model

        transformer, t5_model, clip_model, vae = load_flux_model(
            model_loader_service=object(),
            model_path=Path("fake/flux.safetensors"),
            t5_encoder_path=Path("fake/t5"),
            clip_path=Path("fake/clip"),
            vae_path=Path("fake/vae.safetensors"),
        )
        positive = create_flux_conditioning("positive", t5_encoder=t5_model, clip_model=clip_model)
        latents = flux_denoise_image(transformer, positive)
        image = flux_decode_latents(vae, latents)

        output = os.path.join(self.tmp_dir, "result_flux.png")
        image.save(output)
        self.assertTrue(os.path.exists(output))
