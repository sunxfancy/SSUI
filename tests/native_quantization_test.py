"""Numerical, storage and serialization acceptance for the native quantizer."""
import copy
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F

from ssui.native_quantization import Int8Linear, quantize_model_int8


def storage(model):
    return sum(t.numel() * t.element_size() for t in model.state_dict().values())


class NativeInt8Test(unittest.TestCase):
    def test_storage_error_bound_and_no_dense_weight(self):
        torch.manual_seed(9)
        for dtype in [torch.float32, torch.float16, torch.bfloat16]:
            with self.subTest(dtype=dtype):
                model = nn.Linear(256, 128, bias=False, dtype=dtype)
                original = model.weight.detach().float().clone()
                before = storage(model)
                quantize_model_int8(model)
                self.assertIsInstance(model, Int8Linear)
                self.assertEqual(model._int8_weight.dtype, torch.int8)
                self.assertNotIn('weight', model.state_dict())
                self.assertEqual(list(model.parameters()), [])
                self.assertLess(storage(model), before * .52)
                # Include final fp16/bf16 rounding in the reconstruction bound.
                bound = model._int8_scale / 2 + original.abs() * torch.finfo(dtype).eps
                self.assertTrue(((model.weight.float() - original).abs() <= bound + 1e-7).all())

    def test_zero_extreme_and_tiny_channels_remain_finite(self):
        model = nn.Linear(8, 4, bias=False)
        with torch.no_grad():
            model.weight[0].zero_()
            model.weight[1].fill_(torch.finfo(torch.float32).max)
            model.weight[2].fill_(torch.finfo(torch.float32).tiny)
            model.weight[3].fill_(-.25)
        quantize_model_int8(model)
        self.assertTrue(torch.isfinite(model.weight).all())
        self.assertTrue(torch.isfinite(model._int8_scale).all())
        self.assertEqual(model._int8_weight[0].count_nonzero(), 0)
        self.assertTrue((model._int8_scale > 0).all())
        self.assertTrue(torch.isfinite(model(torch.zeros(1, 8))).all())

    def test_blocked_forward_matches_dense_view_and_bounds_blocks(self):
        model = nn.Linear(32, 17)
        quantize_model_int8(model)
        for shape in [(32,), (2, 32), (2, 5, 32), (0, 32)]:
            x = torch.randn(shape)
            expected = F.linear(x, model.weight, model.bias)
            with patch('ssui.native_quantization._BLOCK_ELEMENTS', 3 * 32):
                with patch.object(model, 'dequantize_weight', wraps=model.dequantize_weight) as dequant:
                    torch.testing.assert_close(model(x), expected, atol=1e-6, rtol=1e-5)
                    self.assertGreater(dequant.call_count, 1)
                    self.assertTrue(all(call.args[1] - call.args[0] <= 3 for call in dequant.call_args_list))

    def test_transformer_inference_with_direct_weight_access(self):
        torch.manual_seed(23)
        model = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(32, 4, dim_feedforward=64, dropout=0, batch_first=True),
            num_layers=2,
        ).eval()
        x = torch.randn(2, 7, 32)
        with torch.inference_mode():
            expected = model(x)
            quantize_model_int8(model)
            actual = model(x)
        self.assertTrue(any(isinstance(layer, Int8Linear) for layer in model.modules()))
        torch.testing.assert_close(actual, expected, atol=.02, rtol=.03)

    def test_empty_feature_dimensions(self):
        for out_features, in_features in [(0, 8), (4, 0), (0, 0)]:
            model = nn.Linear(in_features, out_features)
            x = torch.randn(2, in_features)
            expected = model(x)
            quantize_model_int8(model)
            torch.testing.assert_close(model(x), expected)

    def test_aliases_hooks_and_linear_ties_are_preserved(self):
        a, b = nn.Linear(64, 64), nn.Linear(64, 64)
        b.weight = a.weight
        model = nn.ModuleDict({'a': a, 'alias': a, 'b': b})
        calls = []
        a.register_forward_hook(lambda *args: calls.append(True))
        quantize_model_int8(model)
        self.assertIs(model['a'], a)
        self.assertIs(model['alias'], a)
        self.assertIs(a._int8_weight, b._int8_weight)
        self.assertIs(a._int8_scale, b._int8_scale)
        a(torch.randn(1, 64))
        self.assertEqual(calls, [True])
        quantize_model_int8(model)
        self.assertIs(a._int8_weight, b._int8_weight)

    def test_embedding_ties_and_excluded_aliases_stay_dense(self):
        embedding = nn.Embedding(64, 64)
        head = nn.Linear(64, 64, bias=False)
        head.weight = embedding.weight
        model = nn.ModuleDict({'embedding': embedding, 'head': head, 'other': nn.Linear(64, 64)})
        quantize_model_int8(model)
        self.assertIs(head.weight, embedding.weight)
        self.assertEqual(type(head), nn.Linear)
        self.assertIsInstance(model['other'], Int8Linear)
        shared = nn.Linear(64, 64)
        aliases = nn.ModuleDict({'convert': shared, 'excluded': shared})
        quantize_model_int8(aliases, exclude=('excluded',))
        self.assertEqual(type(shared), nn.Linear)

    def test_invalid_weights_fail_before_any_conversion(self):
        for value in [float('inf'), float('nan')]:
            model = nn.Sequential(nn.Linear(8, 8), nn.Linear(8, 8))
            with torch.no_grad():
                model[1].weight[0, 0] = value
            with self.assertRaisesRegex(ValueError, 'non-finite'):
                quantize_model_int8(model)
            self.assertEqual(type(model[0]), nn.Linear)
        with self.assertRaisesRegex(ValueError, 'meta'):
            quantize_model_int8(nn.Linear(8, 8, device='meta'))

    def test_dtype_changes_preserve_fp32_scales_and_storage(self):
        model = nn.Linear(64, 64)
        with torch.no_grad():
            model.weight.mul_(1e-7)
        quantize_model_int8(model)
        scales = model._int8_scale.clone()
        packed = model._int8_weight.clone()
        for dtype in [torch.float16, torch.bfloat16, torch.float32]:
            model.to(dtype=dtype)
            self.assertEqual(model._int8_scale.dtype, torch.float32)
            self.assertEqual(model.weight.dtype, dtype)
            torch.testing.assert_close(model._int8_scale, scales, atol=0, rtol=0)
            torch.testing.assert_close(model._int8_weight, packed)
            with torch.backends.mkldnn.flags(enabled=False):
                self.assertTrue(torch.isfinite(model(torch.randn(1, 64, dtype=dtype))).all())

    def test_compressed_checkpoint_roundtrip_and_deepcopy(self):
        model = nn.Sequential(nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 32, bias=False)).eval()
        quantize_model_int8(model)
        x = torch.randn(2, 64)
        expected = model(x)
        saved = io.BytesIO()
        torch.save(model.state_dict(), saved)
        saved.seek(0)
        target = nn.Sequential(nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 32, bias=False)).eval()
        quantize_model_int8(target)
        target.load_state_dict(torch.load(saved, weights_only=True))
        torch.testing.assert_close(target(x), expected, atol=0, rtol=0)
        torch.testing.assert_close(copy.deepcopy(model)(x), expected, atol=0, rtol=0)

    def test_image_biasless_lora_sidecar(self):
        from backend.model_manager.load.model_cache.torch_module_autocast.torch_module_autocast import apply_custom_layers_to_model
        from backend.patches.layer_patcher import LayerPatcher
        from backend.patches.layers.lora_layer import LoRALayer
        from backend.patches.model_patch_raw import ModelPatchRaw
        model = nn.Sequential(nn.Linear(64, 64, bias=False))
        quantize_model_int8(model)
        apply_custom_layers_to_model(model)
        x = torch.randn(1, 64)
        original = model(x)
        up, down = torch.randn(64, 2) * .01, torch.randn(2, 64) * .01
        lora = ModelPatchRaw({'0': LoRALayer(up, None, down, 2, None)})
        with LayerPatcher.apply_smart_model_patches(model, [(lora, 1)], prefix='', dtype=torch.float32):
            torch.testing.assert_close(model(x), original + F.linear(F.linear(x, down), up))
        torch.testing.assert_close(model(x), original)

    def test_h3_runner_uses_shared_native_quantizer(self):
        path = Path(__file__).resolve().parents[1] / 'extensions/Video/ssui_video/h3_runner.py'
        spec = importlib.util.spec_from_file_location('test_h3_native_runner', path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        class Pipe:
            transformer = nn.ModuleDict({'proj_in': nn.Linear(64, 64), 'blocks': nn.Linear(64, 64)})
            text_encoder = nn.ModuleDict({'lm_head': nn.Linear(64, 64), 'blocks': nn.Linear(64, 64)})
        pipe = runner._apply_int8(Pipe(), str(Path(__file__).resolve().parents[1] / 'ssui/native_quantization.py'))
        self.assertEqual(type(pipe.transformer['proj_in']), nn.Linear)
        self.assertEqual(type(pipe.text_encoder['lm_head']), nn.Linear)
        self.assertEqual(pipe.transformer['blocks']._int8_weight.dtype, torch.int8)
        self.assertEqual(pipe.text_encoder['blocks']._int8_weight.dtype, torch.int8)
        self.assertTrue(torch.isfinite(pipe.transformer['blocks'](torch.randn(1, 64))).all())

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA device unavailable')
    def test_cuda_move_and_inference(self):
        self._device_roundtrip('cuda', torch.float16)

    @unittest.skipUnless(torch.backends.mps.is_available(), 'MPS device unavailable')
    def test_mps_move_and_inference(self):
        self._device_roundtrip('mps', torch.float16)

    def _device_roundtrip(self, device, dtype):
        model = nn.Linear(128, 128, dtype=dtype).eval()
        quantize_model_int8(model)
        x = torch.randn(2, 128, dtype=dtype)
        expected = model(x)
        model.to(device)
        torch.testing.assert_close(model(x.to(device)).cpu(), expected, atol=.01, rtol=.02)
        self.assertEqual(model._int8_weight.dtype, torch.int8)
        self.assertEqual(model._int8_scale.dtype, torch.float32)
        model.cpu()
        torch.testing.assert_close(model(x), expected)


if __name__ == '__main__':
    unittest.main()
