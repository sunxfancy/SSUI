import unittest
from ssui.SD1 import (
    SD1Model, SD1Condition, SD1Clip, SD1Latent, 
    SD1Denoise, SD1LatentDecode
)
from ssui.base import Prompt, Noise, Image
from ssui.config import SSUIConfig


class TestSD1(unittest.TestCase):
    def setUp(self):
        self.model = SD1Model("D:/StableDiffusion/stable-diffusion-webui/models/Stable-diffusion/animefull-latest.ckpt")
        self.config = SSUIConfig()
        self.config("test")
        self.config["width"] = 512
        self.config["height"] = 512
        self.config["step"] = 20
        self.config["CFG"] = 0.7

    
    def test_sd1_model(self):
        """测试SD1Model的基本功能"""

        
    def test_sd1_clip(self):
        """测试SD1Clip函数"""
        pos, neg = SD1Clip(self.config, self.model, Prompt("A beautiful girl"), Prompt("ugly, bad, word, signiture"))
        self.assertIsInstance(pos, SD1Condition)
        self.assertIsInstance(neg, SD1Condition)
    
    def test_sd1_latent(self):
        """测试SD1Latent类"""
        noise = Noise(self.config)
        latent = SD1Latent(self.config, noise, self.model)
        self.assertEqual(latent.model, self.model)
        self.assertEqual(latent.noise, noise)
    
    def test_sd1_latent_decode(self):
        """测试SD1LatentDecode函数"""
        noise = Noise(self.config)
        latent = SD1Latent(self.config, noise, self.model)
        result = SD1LatentDecode(self.config, self.model, latent)
        self.assertIsInstance(result, Image)
        
