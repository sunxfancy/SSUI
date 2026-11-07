"""CPU regression tests: real tiny tensors and packed quantized inference."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch
import numpy as np
from PIL import Image
from safetensors.torch import save_file

from backend.lance.loading import CheckpointReader, load_streamed
from backend.lance.model import LanceConfig, NaiveCache, Qwen2MoTForCausalLM
from backend.lance.quantization import (
    QuantizedLinear,
    quantize_linear_layers,
    storage_bytes,
)
from backend.lance.transformer import LanceTransformer


def tiny_config():
    return LanceConfig(
        vocab_size=32,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=1,
        rope_scaling={"rope_type": "mrope", "mrope_section": [2, 2, 4]},
    )


class LanceQuantizationTest(unittest.TestCase):
    def test_quantized_linear_accuracy_and_actual_packed_storage(self):
        torch.manual_seed(9)
        linear = torch.nn.Linear(128, 128).eval()
        x = torch.randn(7, 128)
        expected = linear(x)
        for mode, tolerance, storage_ratio in [
            ("nf4", 0.14, 0.35),
            ("int8", 0.02, 0.6),
        ]:
            with self.subTest(mode=mode):
                quantized = QuantizedLinear(linear.weight, linear.bias, mode=mode)
                output = quantized(x)
                relative_error = (output - expected).norm() / expected.norm()
                self.assertLess(relative_error, tolerance)
                dense_bf16_bytes = (linear.weight.numel() + linear.bias.numel()) * 2
                self.assertLess(
                    storage_bytes(quantized), dense_bf16_bytes * storage_ratio
                )
                self.assertEqual(list(quantized.parameters()), [])
                self.assertFalse(hasattr(quantized, "weight"))

    def test_nf4_handles_non_block_aligned_and_zero_weights(self):
        for mode in ("nf4", "int8"):
            for weight in (torch.zeros(3, 7), torch.randn(3, 7)):
                q = QuantizedLinear(weight, mode=mode)
                self.assertEqual(q.dequantize().shape, weight.shape)
                self.assertTrue(torch.isfinite(q(torch.ones(2, 7))).all())
                if weight.count_nonzero() == 0:
                    torch.testing.assert_close(q.dequantize(), weight)

    def test_moving_packed_weights_and_state_roundtrip(self):
        for mode in ("nf4", "int8"):
            q = QuantizedLinear(torch.randn(8, 19), torch.randn(8), mode=mode)
            state = copy.deepcopy(q.state_dict())
            other = QuantizedLinear(torch.zeros(8, 19), torch.zeros(8), mode=mode)
            other.load_state_dict(state)
            x = torch.randn(3, 19)
            torch.testing.assert_close(q(x), other.to("cpu")(x))


class LanceTransformerTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.model = Qwen2MoTForCausalLM(tiny_config()).eval()

    def test_causal_cache_matches_full_forward_including_multi_token_append(self):
        ids = torch.tensor([2, 4, 8, 6, 3, 5])
        positions = torch.arange(6)
        expected = self.model(
            packed_text_ids=ids, packed_query_position_ids=positions
        ).packed_query_sequence
        for split in (1, 3, 5):
            cache = NaiveCache(2)
            self.model(
                packed_text_ids=ids[:split],
                packed_query_position_ids=positions[:split],
                past_key_values=cache,
            )
            actual = self.model(
                packed_text_ids=ids[split:],
                packed_query_position_ids=positions[split:],
                past_key_values=cache,
            ).packed_query_sequence
            torch.testing.assert_close(actual, expected[split:], atol=1e-5, rtol=1e-5)
            self.assertEqual(cache.seq_lens, len(ids))

    def test_experts_route_and_noise_queries_do_not_change_cache(self):
        ids = torch.tensor([1, 2, 3])
        cache = NaiveCache(2)
        self.model(
            packed_text_ids=ids,
            packed_query_position_ids=torch.arange(3),
            past_key_values=cache,
        )
        before = cache.key_cache[0].clone()
        x = torch.randn(4, 32)
        kwargs = dict(
            packed_query_sequence=x,
            packed_query_position_ids=torch.arange(4),
            past_key_values=cache,
            update_past_key_values=False,
            is_causal=False,
        )
        understanding = self.model(**kwargs).packed_query_sequence
        generation = self.model(
            **kwargs,
            mode="gen",
            packed_vae_token_indexes=torch.tensor([1, 2]),
            packed_text_indexes=torch.tensor([0, 3]),
        ).packed_query_sequence
        self.assertFalse(torch.allclose(generation, understanding))
        torch.testing.assert_close(cache.key_cache[0], before)
        self.assertEqual(cache.seq_lens, 3)

    def test_both_experts_run_in_nf4_and_int8(self):
        for mode in ("nf4", "int8"):
            model = copy.deepcopy(self.model)
            # Apply to both attention and MLP experts, as the streaming loader does.
            quantize_linear_layers(model.model.layers, mode)
            self.assertIsInstance(
                model.model.layers[0].self_attn.q_proj, QuantizedLinear
            )
            self.assertIsInstance(
                model.model.layers[0].self_attn.q_proj_moe_gen, QuantizedLinear
            )
            out = model(
                packed_text_ids=torch.tensor([1, 2, 3]),
                packed_query_position_ids=torch.arange(3),
                mode="gen",
                packed_vae_token_indexes=torch.tensor([1]),
                packed_text_indexes=torch.tensor([0, 2]),
            )
            self.assertEqual(out.packed_query_sequence.shape, (3, 32))
            self.assertTrue(torch.isfinite(out.packed_query_sequence).all())


class LanceLoadingAndDenoisingTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(5)
        self.dense = LanceTransformer(tiny_config()).eval()

    def test_streamed_loading_from_meta_is_strict_and_quantizes_both_experts(self):
        with tempfile.TemporaryDirectory() as folder:
            save_file(self.dense.state_dict(), str(Path(folder) / "model.safetensors"))
            reader = CheckpointReader(folder)
            for mode in ("none", "nf4", "int8"):
                with torch.device("meta"):
                    model = LanceTransformer(tiny_config())
                count = load_streamed(model, reader, quantization=mode)
                self.assertEqual(count, 28 if mode != "none" else 0)
                self.assertFalse(any(p.is_meta for p in model.parameters()))
                if mode != "none":
                    self.assertIsInstance(
                        model.language_model.model.layers[1].mlp_moe_gen.down_proj,
                        QuantizedLinear,
                    )
                else:
                    for name, value in self.dense.state_dict().items():
                        torch.testing.assert_close(model.state_dict()[name], value)
                out = model.language_model(
                    packed_text_ids=torch.tensor([1]),
                    packed_query_position_ids=torch.tensor([0]),
                )
                self.assertTrue(torch.isfinite(out.packed_query_sequence).all())

    def test_missing_or_wrong_shape_weight_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "model.safetensors")
            state = self.dense.state_dict()
            state.pop("llm2vae.bias")
            save_file(state, path)
            with self.assertRaisesRegex(ValueError, "missing"):
                load_streamed(self.dense, CheckpointReader(folder))
            state = self.dense.state_dict()
            state["llm2vae.bias"] = torch.zeros(2)
            save_file(state, path)
            with self.assertRaisesRegex(ValueError, "shape mismatch"):
                load_streamed(self.dense, CheckpointReader(folder))

    def test_quantized_video_denoise_pins_first_frame_and_keeps_cache_constant(self):
        model = self.dense
        quantize_linear_layers(model.language_model.model.layers, "nf4")
        # Tiny video table: two temporal latent slices, 2x2 spatial tokens.
        model.latent_pos_embed.pos_embed = torch.nn.Parameter(
            torch.randn(8192, 32), requires_grad=False
        )
        cache = NaiveCache(2)
        model.language_model(
            packed_text_ids=torch.tensor([1, 2]),
            packed_query_position_ids=torch.arange(2),
            past_key_values=cache,
        )
        inp = model.prepare_video_latent(
            [2], [2], [(5, 32, 32)], dict(start_of_image=3, end_of_image=4)
        )
        for key in ("packed_indexes", "packed_key_value_indexes", "key_values_lens"):
            inp.pop(key, None)
        before = inp["packed_init_noises"][:4].clone()
        original_cache = cache.key_cache[0].clone()
        result, *_ = model.generate_image(
            **inp,
            past_key_values=cache,
            num_timesteps=2,
            cfg_text_scale=1,
            frame_condition_token_indexes=torch.arange(4),
        )
        torch.testing.assert_close(result[0][:4], before)
        self.assertFalse(torch.allclose(result[0][4:], inp["packed_init_noises"][4:]))
        torch.testing.assert_close(cache.key_cache[0], original_cache)
        positions = inp["packed_position_ids"]
        self.assertEqual(positions.shape, (3, 10))
        self.assertEqual(int(positions[0, 5] - positions[0, 1]), 2)


class _TinyTokenizer:
    unk_token_id = None

    def convert_tokens_to_ids(self, token):
        return {
            "<|im_start|>": 1,
            "<|im_end|>": 2,
            "<|vision_start|>": 3,
            "<|vision_end|>": 4,
        }[token]

    def encode(self, text, **kwargs):
        return [5 + ord(char) % 27 for char in text]

    def decode(self, tokens):
        return "answer " + " ".join(str(token) for token in tokens)


class _TinyVAE(torch.nn.Module):
    """Shape-faithful fixture: tests pipeline wiring, not VAE image quality."""

    def __init__(self, *args, dtype=torch.float32, device="cpu", **kwargs):
        super().__init__()
        self.anchor = torch.nn.Parameter(
            torch.zeros(1, dtype=dtype, device=device), requires_grad=False
        )

    def encode(self, x):
        if x.ndim == 4:
            return torch.nn.functional.avg_pool2d(x[:, :1], 16).repeat(1, 48, 1, 1)
        return torch.nn.functional.avg_pool3d(x[:, :1, ::4], (1, 16, 16)).repeat(
            1, 48, 1, 1, 1
        )

    def decode_video(self, x):
        return torch.nn.functional.interpolate(
            x[:, :3], size=((x.shape[2] - 1) * 4 + 1, x.shape[3] * 16, x.shape[4] * 16)
        ).tanh()

    def decode(self, x):
        return (
            self.decode_video(x.unsqueeze(2)).squeeze(2)
            if x.ndim == 4
            else self.decode_video(x)
        )


class LancePipelineIntegrationTest(unittest.TestCase):
    def test_bundle_load_quantization_all_task_paths_and_unload(self):
        from transformers import Qwen2VLImageProcessor
        from backend.lance import LancePipeline
        from backend.lance.vision import Qwen2_5_VisionTransformerPretrainedModel

        vision_config = dict(
            hidden_size=32,
            intermediate_size=64,
            out_hidden_size=32,
            num_heads=2,
            depth=1,
            hidden_act="silu",
            spatial_merge_size=2,
            patch_size=14,
            temporal_patch_size=2,
            in_channels=3,
            fullatt_block_indexes=[0],
            window_size=112,
            _attn_implementation="sdpa",
        )
        torch.manual_seed(123)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            vision_dir = root / "Qwen2.5-VL-ViT"
            vision_dir.mkdir()
            (vision_dir / "config.json").write_text(json.dumps(vision_config))
            vision = Qwen2_5_VisionTransformerPretrainedModel(
                SimpleNamespace(**vision_config)
            )
            save_file(vision.state_dict(), str(vision_dir / "vit.safetensors"))
            (root / "Wan2.2_VAE.pth").touch()
            for variant, rows in [("Lance_3B", 4096), ("Lance_3B_Video", 8192)]:
                folder_path = root / variant
                folder_path.mkdir()
                (folder_path / "llm_config.json").write_text(
                    json.dumps(vars(tiny_config()))
                )
                model = LanceTransformer(tiny_config(), position_rows=rows)
                save_file(model.state_dict(), str(folder_path / "model.safetensors"))
            processor = Qwen2VLImageProcessor(min_pixels=28 * 28, max_pixels=56 * 56)
            with (
                patch(
                    "transformers.Qwen2TokenizerFast.from_pretrained",
                    return_value=_TinyTokenizer(),
                ),
                patch("transformers.Qwen2VLImageProcessor", return_value=processor),
                patch("backend.lance.wan_vae.LanceWanVAE", _TinyVAE),
                patch("backend.lance.conditioning.LANCE_VIDEO_VAE_RESOLUTION", 64),
                patch("backend.lance.conditioning.LANCE_VIDEO_VIT_RESOLUTION", 56),
            ):
                image = Image.new("RGB", (32, 32), "red")
                video = np.stack([np.asarray(image)] * 5)
                for variant, tasks in [
                    ("image", ["t2i", "image_edit", "x2t_image"]),
                    ("video", ["t2v", "i2v", "video_edit", "x2t_video"]),
                ]:
                    pipeline = LancePipeline.from_pretrained(
                        root, variant=variant, quantization="nf4", device="cpu"
                    )
                    self.assertEqual(pipeline.quantized_linear_count, 28)
                    rng_state = torch.random.get_rng_state().clone()
                    for task in tasks:
                        with self.subTest(task=task):
                            out = pipeline(
                                "test",
                                task=task,
                                image=image,
                                video=video,
                                width=32,
                                height=32,
                                num_frames=5,
                                num_inference_steps=1,
                                guidance_scale=2,
                                max_new_tokens=3,
                            )
                            if task.startswith("x2t"):
                                self.assertTrue(out.text)
                            elif task in ("t2i", "image_edit"):
                                self.assertIsInstance(out.images[0], Image.Image)
                            else:
                                self.assertEqual(len(out.frames), 5)
                    torch.testing.assert_close(torch.random.get_rng_state(), rng_state)
                    if variant == "video":
                        with self.assertRaisesRegex(ValueError, "4n"):
                            pipeline(task="t2v", num_frames=6)
                    else:
                        with self.assertRaisesRegex(ValueError, "Unsupported"):
                            pipeline(task="bad")
                    pipeline.unload()
                    self.assertIsNone(pipeline.bagel)
                    self.assertIsNone(pipeline.vae)
                    with self.assertRaisesRegex(RuntimeError, "unloaded"):
                        pipeline("test")


if __name__ == "__main__":
    unittest.main()
