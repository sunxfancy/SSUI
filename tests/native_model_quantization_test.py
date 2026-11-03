"""Small real model architectures; no checkpoint downloads or GPU required.

These compare inference on random weights, not generated-content quality.
"""
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

from ssui.native_quantization import Int8Linear, quantize_model_int8


ROOT = Path(__file__).resolve().parents[1]


def stored_bytes(model):
    return sum(t.numel() * t.element_size() for t in model.state_dict().values())


class NativeModelQuantizationTest(unittest.TestCase):
    def test_small_qwen_cached_generation(self):
        from transformers import Qwen2Config, Qwen2ForCausalLM
        torch.manual_seed(13)
        model = Qwen2ForCausalLM(Qwen2Config(
            vocab_size=128, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
            num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=64,
            tie_word_embeddings=True,
        )).eval()
        tokens = torch.tensor([[1, 3, 5, 7, 11]])
        before = stored_bytes(model)
        with torch.inference_mode():
            reference = model(tokens).logits
            quantize_model_int8(model)
            actual = model(tokens).logits
            generated = model.generate(tokens, max_new_tokens=3, do_sample=False, pad_token_id=0)
        torch.testing.assert_close(actual, reference, atol=.02, rtol=.03)
        self.assertIs(model.lm_head.weight, model.model.embed_tokens.weight)
        self.assertLess(stored_bytes(model), before)
        self.assertEqual(generated.shape, (1, 8))

    def test_small_diffusers_unet_cross_attention(self):
        from diffusers import UNet2DConditionModel
        torch.manual_seed(17)
        model = UNet2DConditionModel(
            sample_size=8, in_channels=4, out_channels=4, layers_per_block=1,
            block_out_channels=(16, 32), norm_num_groups=4,
            down_block_types=('CrossAttnDownBlock2D', 'DownBlock2D'),
            up_block_types=('UpBlock2D', 'CrossAttnUpBlock2D'),
            cross_attention_dim=32, attention_head_dim=4,
        ).eval()
        sample, context = torch.randn(1, 4, 8, 8), torch.randn(1, 4, 32)
        before = stored_bytes(model)
        with torch.inference_mode():
            reference = model(sample, 10, encoder_hidden_states=context).sample
            quantize_model_int8(model)
            actual = model(sample, 10, encoder_hidden_states=context).sample
        torch.testing.assert_close(actual, reference, atol=.02, rtol=.04)
        self.assertLess(stored_bytes(model), before)
        self.assertTrue(torch.isfinite(actual).all())

    def test_vendored_wan_video_dit(self):
        # Load the real model module without importing every optional video model
        # through diffsynth/__init__.py. Relative imports resolve to real files.
        package = types.ModuleType('_ssui_wan_model_test')
        package.__path__ = [str(ROOT / 'extensions/Video/diffsynth/models')]
        with patch.dict(sys.modules, {package.__name__: package}):
            wan = importlib.import_module(package.__name__ + '.wan_video_dit')
        wan.FLASH_ATTN_3_AVAILABLE = wan.FLASH_ATTN_2_AVAILABLE = wan.SAGE_ATTN_AVAILABLE = False
        torch.manual_seed(19)
        model = wan.WanModel(
            dim=32, in_dim=4, ffn_dim=64, out_dim=4, text_dim=32, freq_dim=16,
            eps=1e-6, patch_size=(1, 2, 2), num_heads=4, num_layers=2, has_image_input=False,
        ).eval()
        sample, timestep, context = torch.randn(1, 4, 2, 4, 4), torch.tensor([10.]), torch.randn(1, 4, 32)
        before = stored_bytes(model)
        with torch.inference_mode():
            reference = model(sample, timestep, context)
            quantize_model_int8(model)
            actual = model(sample, timestep, context)
        torch.testing.assert_close(actual, reference, atol=.03, rtol=.05)
        self.assertLess(stored_bytes(model), before)
        self.assertTrue(torch.isfinite(actual).all())


class NativeLoRATest(unittest.TestCase):
    def test_low_rank_sidecar_forward_direct_weight_and_checkpoint(self):
        torch.manual_seed(29)
        model = nn.Linear(64, 32)
        quantize_model_int8(model)
        packed = model._int8_weight.clone()
        x, up, down = torch.randn(2, 64), torch.randn(32, 4) * .01, torch.randn(4, 64) * .01
        baseline = model(x)
        model.add_lora(up, down, .75)
        expected = baseline + F.linear(F.linear(x, down), up) * .75
        torch.testing.assert_close(model(x), expected)
        torch.testing.assert_close(F.linear(x, model.weight, model.bias), expected, atol=1e-6, rtol=1e-5)
        torch.testing.assert_close(model._int8_weight, packed, atol=0, rtol=0)
        target = nn.Linear(64, 32)
        quantize_model_int8(target)
        target.load_state_dict(model.state_dict())
        torch.testing.assert_close(target(x), expected)
        model.half()
        self.assertEqual(model._int8_loras[0].alpha.dtype, torch.float32)
        self.assertEqual(model._int8_scale.dtype, torch.float32)

    def test_dense_delta_merge_requantizes_and_retains_aliases(self):
        model = nn.Linear(64, 32, bias=False)
        quantize_model_int8(model)
        packed, scale = model._int8_weight, model._int8_scale
        original = model.weight.clone()
        delta = torch.randn(32, 64) * .001
        model.merge_weight_delta(delta)
        self.assertIs(model._int8_weight, packed)
        self.assertIs(model._int8_scale, scale)
        self.assertTrue(((model.weight - original - delta).abs() <= model._int8_scale / 2 + 1e-7).all())
        unchanged = model._int8_weight.clone()
        delta[-1, 0] = float('inf')
        with self.assertRaisesRegex(ValueError, 'finite'):
            model.merge_weight_delta(delta)
        torch.testing.assert_close(model._int8_weight, unchanged)

    def test_vendored_general_lora_loader(self):
        path = ROOT / 'extensions/Video/diffsynth/lora/__init__.py'
        spec = importlib.util.spec_from_file_location('_ssui_native_lora_test', path)
        loader_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader_module)
        model = nn.Sequential(nn.Linear(64, 32))
        quantize_model_int8(model)
        x, up, down = torch.randn(2, 64), torch.randn(32, 4) * .01, torch.randn(4, 64) * .01
        baseline = model(x)
        loader_module.GeneralLoRALoader().load(model, {'0.lora_B.default.weight': up, '0.lora_A.default.weight': down}, alpha=.5)
        torch.testing.assert_close(model(x), baseline + F.linear(F.linear(x, down), up) * .5)
        self.assertIsInstance(model[0], Int8Linear)


class NativeCheckpointLoRATest(unittest.TestCase):
    @staticmethod
    def _loaders():
        # Execute the exact loader classes without eagerly importing unrelated
        # optional model architectures. Numerical work uses real Torch modules.
        import ast
        path = ROOT / 'extensions/Video/diffsynth/models/lora.py'
        tree = ast.parse(path.read_text(), filename=str(path))
        wanted = [node for node in tree.body if
                  isinstance(node, ast.ClassDef) and node.name in ('LoRAFromCivitai', 'GeneralLoRAFromPeft')
                  or isinstance(node, ast.ImportFrom) and node.module == 'ssui.native_quantization']
        env = {'torch': torch}
        for name in ['SDUNet', 'SDXLUNet', 'SD3DiT', 'HunyuanDiT', 'FluxDiT', 'CogDiT', 'WanModel']:
            env[name] = nn.Module
        exec(compile(ast.Module(body=wanted, type_ignores=[]), str(path), 'exec'), env)
        return env['LoRAFromCivitai'], env['GeneralLoRAFromPeft']

    def test_peft_matching_mixed_weights_and_serialized_sidecars(self):
        _, Peft = self._loaders()
        model = nn.Sequential(nn.Linear(64, 32), nn.Linear(32, 16))
        # Excluded layers still exercise the original dense merge path.
        quantize_model_int8(model, exclude=('1',))
        x = torch.randn(2, 64)
        original0, original1 = model[0](x), model[1].weight.detach().clone()
        up0, down0 = torch.randn(32, 4) * .01, torch.randn(4, 64) * .01
        up1, down1 = torch.randn(16, 4) * .01, torch.randn(4, 32) * .01
        state = {'0.lora_B.default.weight': up0, '0.lora_A.default.weight': down0,
                 '1.lora_B.default.weight': up1, '1.lora_A.default.weight': down1}
        loader = Peft()
        self.assertIsNotNone(loader.match(model, state))
        loader.load(model, state, alpha=.5)
        expected0 = original0 + F.linear(F.linear(x, down0), up0) * .5
        torch.testing.assert_close(model[0](x), expected0)
        torch.testing.assert_close(model[1].weight, original1 + (up1 @ down1) * .5)
        target = nn.Sequential(nn.Linear(64, 32), nn.Linear(32, 16))
        quantize_model_int8(target, exclude=('1',))
        target.load_state_dict(model.state_dict())
        torch.testing.assert_close(target(x), model(x))

    def test_civitai_matching_and_quantized_delta_merge(self):
        Civitai, _ = self._loaders()
        class Model(nn.Module):
            def __init__(self):
                super().__init__()
                self.layer = nn.Linear(64, 32)
            @staticmethod
            def state_dict_converter():
                return types.SimpleNamespace(from_diffusers=lambda value: value, from_civitai=lambda value: value)
        model = Model()
        quantize_model_int8(model)
        original = model.layer.weight.clone()
        up, down = torch.randn(32, 4) * .01, torch.randn(4, 64) * .01
        state = {'layer.lora_B.weight': up, 'layer.lora_A.weight': down}
        loader = Civitai()
        loader.supported_model_classes, loader.lora_prefix = [Model], ['']
        self.assertIsNotNone(loader.match(model, state))
        loader.load(model, state, '', alpha=.5)
        expected_delta = (.5 * (up.half() @ down.half())).float()
        bound = model.layer._int8_scale / 2 + 1e-7
        self.assertTrue(((model.layer.weight - original - expected_delta).abs() <= bound).all())


if __name__ == '__main__':
    unittest.main()
