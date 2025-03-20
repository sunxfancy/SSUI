import unittest
from ssui_api.model import (
    ModelLoaderService,
    load_flux_model,
    load_model,
    load_sdxl_model,
)
from ssui_api.conditioning import (
    create_conditioning,
    create_flux_conditioning,
    create_sdxl_conditioning,
)
from ssui_api.denoise import (
    denoise_image,
    decode_latents,
    flux_decode_latents,
    flux_denoise_image,
)
import torch
from pathlib import Path

torch.no_grad()


def generate_image(model_path: Path, positive: str, negative: str):
    model_loader_service = ModelLoaderService()
    unet, clip, vae = load_model(
        model_loader_service=model_loader_service, model_path=model_path
    )

    positive_conditioning = create_conditioning(positive, clip)
    negative_conditioning = create_conditioning(negative, clip)

    result_latents = denoise_image(
        unet,
        positive_conditioning,
        negative_conditioning,
        seed=123454321,
        width=512,
        height=512,
        scheduler_name="ddim",
        cfg_scale=7.5,
        steps=30,
    )

    image = decode_latents(vae, result_latents)
    image.save("result.png")


def generate_sdxl_image(model_path: Path, positive: str, negative: str):
    model_loader_service = ModelLoaderService()
    unet, clip, clip2, vae = load_sdxl_model(model_loader_service, model_path)

    positive_conditioning = create_sdxl_conditioning(
        positive, "", clip, clip2, 1024, 1024, 0, 0, 1024, 1024
    )
    negative_conditioning = create_sdxl_conditioning(
        negative, "", clip, clip2, 1024, 1024, 0, 0, 1024, 1024
    )

    result_latents = denoise_image(
        unet,
        positive_conditioning,
        negative_conditioning,
        seed=987654321,
        width=1024,
        height=1024,
        scheduler_name="dpmpp_2m_sde_k",
        cfg_scale=6,
        steps=32,
    )

    image = decode_latents(vae, result_latents)
    image.save("result2.png")


def generate_flux_image(
    model_path: Path,
    t5_encoder_path: Path,
    clip_path: Path,
    vae_path: Path,
    positive: str,
    negative: str,
):
    model_loader_service = ModelLoaderService()
    transformer, t5_model, clip_model, vae = load_flux_model(
        model_loader_service=model_loader_service,
        model_path=model_path,
        t5_encoder_path=t5_encoder_path,
        clip_path=clip_path,
        vae_path=vae_path,
    )

    positive_conditioning = create_flux_conditioning(
        positive, t5_encoder=t5_model, clip_model=clip_model
    )
    result_latents = flux_denoise_image(transformer, positive_conditioning)
    image = flux_decode_latents(vae, result_latents)
    image.save("result3.png")


class TestBackend(unittest.TestCase):
    def test_backend(self):
        generate_image(
            Path(
                "D:\\StableDiffusion\\stable-diffusion-webui\\models\\Stable-diffusion\\anything-v3-2700c435.ckpt"
            ),
            "a beautiful girl, masterpiece, best quality",
            "a bad image",
        )

    def test_sdxl(self):
        generate_sdxl_image(
            Path("H:\\SSUI\\server\\AnythingXL_xl.safetensors"),
            "a beautiful girl in a red dress, masterpiece, best quality",
            "a bad image",
        )

    def test_flux(self):
        generate_flux_image(
            Path(
                "C:\\Users\\sunxf\\InvokeAI\\models\\flux\\main\\FLUX Schnell (Quantized).safetensors"
            ),
            Path(
                "C:\\Users\\sunxf\\InvokeAI\\models\\any\\t5_encoder\\t5_bnb_int8_quantized_encoder"
            ),
            Path(
                "C:\\Users\\sunxf\\InvokeAI\\models\\any\\clip_embed\\clip-vit-large-patch14"
            ),
            Path("C:\\Users\\sunxf\\InvokeAI\\models\\flux\\vae\\FLUX.safetensors"),
            positive="a beautiful girl in a red dress",
            negative="a bad image",
        )
