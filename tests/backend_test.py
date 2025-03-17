import unittest
from ssui_api.model import ModelLoaderService, load_model
from ssui_api.conditioning import create_conditioning
from ssui_api.denoise import denoise_image, decode_latents
import torch
from pathlib import Path

torch.no_grad()
def generate_image(positive: str, negative: str):
    model_path = Path(
        "D:\\StableDiffusion\\stable-diffusion-webui\\models\\Stable-diffusion\\anything-v3-2700c435.ckpt"
    )

    model_loader_service = ModelLoaderService()
    unet, clip, vae = load_model(model_loader_service=model_loader_service, model_path=model_path)

    positive_conditioning = create_conditioning(positive, clip)
    negative_conditioning = create_conditioning(negative, clip)

    result_latents = denoise_image(unet, positive_conditioning, negative_conditioning, seed=123454321, width=512, height=512, scheduler_name="ddim", cfg_scale=7.5, steps=30)

    image = decode_latents(vae, result_latents)
    image.save("result.png")


class TestBackend(unittest.TestCase):
    def test_backend(self):
        generate_image("a beautiful girl, masterpiece, best quality", "a bad image")
