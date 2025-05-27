import unittest
from tests.utils import should_run_slow_tests

@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestSD1(unittest.TestCase):
    def setUp(self):
        from ssui_image.SD1 import SD1Model
        from ssui.config import SSUIConfig
        from ssui.base import Prompt
        self.model = SD1Model.load("D:\\StableDiffusion\\stable-diffusion-webui\\models\\Stable-diffusion\\anything-v3-2700c435.ckpt")
        self.config = SSUIConfig()
        self.config.set_prepared(False)

        self.positive = Prompt("a beautiful girl, masterpiece, best quality")
        self.negative = Prompt("a bad image")

    
    def test_workflow(self):
        from ssui_image.SD1 import (
            SD1Clip, SD1Latent, 
            SD1Denoise, SD1LatentDecode
        )
        positive, negative = SD1Clip(self.config("Prompt To Condition"), self.model, self.positive, self.negative)
        latent = SD1Latent(self.config("Create Empty Latent"))
        latent = SD1Denoise(self.config("Denoise"), self.model, latent, positive, negative)
        image = SD1LatentDecode(self.config("Latent to Image"), self.model, latent)
        image._image.save("result2.png")


@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestSDXL(unittest.TestCase):
    def setUp(self):
        from ssui_image.SDXL import SDXLModel
        from ssui.config import SSUIConfig
        from ssui.base import Prompt
        self.model = SDXLModel.load("C:\\Users\\sunxf\\InvokeAI\\models\\sdxl\\main\\Juggernaut XL v9")
        self.config = SSUIConfig()
        self.config.set_prepared(False)

        self.positive = Prompt("a beautiful girl in a red dress, masterpiece, best quality")
        self.negative = Prompt("a bad image")
    
    def test_workflow(self):
        from ssui_image.SDXL import (
            SDXLClip, SDXLLatent, 
            SDXLDenoise, SDXLLatentDecode
        )
        positive, negative = SDXLClip(self.config("Prompt To Condition"), self.model, self.positive, self.negative)
        latent = SDXLLatent(self.config("Create Empty Latent"))
        latent = SDXLDenoise(self.config("Denoise"), self.model, latent, positive, negative)
        image = SDXLLatentDecode(self.config("Latent to Image"), self.model, latent)
        image._image.save("result_sdxl.png")


@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestFlux(unittest.TestCase):
    def setUp(self):
        from ssui_image.Flux import FluxModel
        from ssui.config import SSUIConfig
        from ssui.base import Prompt
        self.model = FluxModel.load(
            model_path="C:\\Users\\sunxf\\InvokeAI\\models\\flux\\main\\FLUX Schnell (Quantized).safetensors",
            t5_encoder_path="C:\\Users\\sunxf\\InvokeAI\\models\\any\\t5_encoder\\t5_bnb_int8_quantized_encoder",
            clip_path="C:\\Users\\sunxf\\InvokeAI\\models\\any\\clip_embed\\clip-vit-large-patch14",
            vae_path="C:\\Users\\sunxf\\InvokeAI\\models\\flux\\vae\\FLUX.safetensors"
        )
        self.config = SSUIConfig()
        self.config.set_prepared(False)

        self.positive = Prompt("a beautiful girl in a red dress")
        self.negative = Prompt("a bad image")
    
    def test_workflow(self):
        from ssui_image.Flux import (
            FluxClip, FluxLatent, 
            FluxDenoise, FluxLatentDecode
        )
        positive, negative = FluxClip(self.config("Prompt To Condition"), self.model, self.positive, self.negative)
        latent = FluxLatent(self.config("Create Empty Latent"))
        latent = FluxDenoise(self.config("Denoise"), self.model, latent, positive, negative)
        image = FluxLatentDecode(self.config("Latent to Image"), self.model, latent)
        image._image.save("result_flux.png")

@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestSD1lora(unittest.TestCase):
    def setUp(self):
        from ssui_image.SD1 import SD1Model,SD1Lora
        from ssui.config import SSUIConfig
        from ssui.base import Prompt
        loraPath = ["D:\\work\\github_code\\SSUI\\test_models\\dilireba.safetensors","D:\\work\\github_code\\SSUI\\test_models\\jirai_v2.safetensors"]
        self.model = SD1Model.load("D:\\work\\github_code\\SSUI\\test_models\\aingdiffusion_v40.safetensors")
        self.loras = SD1Lora.load(loraPath)
        self.config = SSUIConfig()
        self.config.set_prepared(False)

        self.positive = Prompt("a beautiful girl, masterpiece, best quality")
        self.negative = Prompt("a bad image")

    
    def test_workflow(self):
        from ssui_image.SD1 import (
            SD1Clip, SD1Latent, 
            SD1Denoise, SD1LatentDecode,SD1MergeLora
        )
        self.model = SD1MergeLora(self.config("Apply Lora"), self.model, self.loras)
        positive, negative = SD1Clip(self.config("Prompt To Condition"), self.model, self.positive, self.negative)
        latent = SD1Latent(self.config("Create Empty Latent"))
        latent = SD1Denoise(self.config("Denoise"), self.model, latent, positive, negative)
        image = SD1LatentDecode(self.config("Latent to Image"), self.model, latent)
        image._image.save("sd1Lora.png")

@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestSDXLlora(unittest.TestCase):
    def setUp(self):
        from ssui_image.SDXL import SDXLModel,SDXLLora
        from ssui.config import SSUIConfig
        from ssui.base import Prompt
        self.model = SDXLModel.load("D:\\work\\github_code\\SSUI_NEW\\test_models\\Juggernaut XL v9")
        self.config = SSUIConfig()
        self.config.set_prepared(False)
        loraPath = ["D:\\work\\github_code\\SSUI_NEW\\test_models\\sdxl lora\\kallen-1.safetensors","D:\\work\\github_code\\SSUI_NEW\\test_models\\sdxl lora\\SDXL_Lora_paffypafuricia_animagine.safetensors"]
        self.loras = SDXLLora.load(loraPath)
        self.config = SSUIConfig()
        self.config.set_prepared(False)

        self.positive = Prompt("a beautiful girl, masterpiece, best quality")
        self.negative = Prompt("a bad image")

    
    def test_workflow(self):
        from ssui_image.SDXL import (
            SDXLClip, SDXLLatent, 
            SDXLDenoise, SDXLLatentDecode,SDXLMergeLora
        )
        self.model = SDXLMergeLora(self.config("Apply Lora"), self.model, self.loras)
        positive, negative = SDXLClip(self.config("Prompt To Condition"), self.model, self.positive, self.negative)
        latent = SDXLLatent(self.config("Create Empty Latent"))
        latent = SDXLDenoise(self.config("Denoise"), self.model, latent, positive, negative)
        image = SDXLLatentDecode(self.config("Latent to Image"), self.model, latent)
        image._image.save("sdXLLora.png")