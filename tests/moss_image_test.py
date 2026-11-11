import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from torch import nn
from safetensors.torch import save_file

from backend.moss_image.dit import MOSSImageDiT
from backend.moss_image.pipeline import MOSSPipeline, format_prompt, sampling_sigmas
from backend.moss_image.qwen_ops import torch_chunk_gated_delta_rule
from backend.moss_image.text_encoder import TextEncoder
from backend.moss_image.vae import Flux2VAE
from backend.moss_image.weights import load_component, text_weight_key, weight_shards


class MOSSImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.previous_threads)

    def test_text_encoder_matches_upstream_golden_across_chunk_boundary(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/moss_image/qwen35_hf53.json").read_text())
        model = TextEncoder(fixture["config"]).eval()
        with torch.no_grad():
            for index, p in enumerate(model.parameters()):
                p.copy_(torch.sin(torch.arange(p.numel()).float() * .17 + index).reshape(p.shape) * .15)
            for length, reference in fixture["outputs"].items():
                ids = (torch.arange(int(length)) % fixture["config"]["vocab_size"])[None]
                torch.testing.assert_close(model(ids)[0], torch.tensor(reference), atol=1e-6, rtol=1e-5)
            ids = torch.tensor([[0, 1, 2, 0], [3, 4, 0, 0]])
            mask = torch.tensor([[0, 1, 1, 0], [1, 1, 0, 0]])
            encoded = model(ids, mask)
            torch.testing.assert_close(encoded[0, mask[0].bool()], model(torch.tensor([[1, 2]]))[0])
            self.assertEqual(encoded[~mask.bool()].abs().sum().item(), 0)

    def test_chunk_delta_rule_matches_independent_recurrent_equations(self):
        torch.manual_seed(12)
        q, k, v = [torch.randn(1, 67, 2, 4) for _ in range(3)]
        beta = torch.rand(1, 67, 2)
        g = -torch.rand(1, 67, 2)
        actual, _ = torch_chunk_gated_delta_rule(q, k, v, g, beta, use_qk_l2norm_in_kernel=True)
        q = q * torch.rsqrt(q.square().sum(-1, keepdim=True) + 1e-6) / 2
        k = k * torch.rsqrt(k.square().sum(-1, keepdim=True) + 1e-6)
        state = torch.zeros(1, 2, 4, 4)
        expected = []
        for i in range(67):
            state = state * g[:, i].exp()[..., None, None]
            update = beta[:, i, :, None] * (v[:, i] - torch.einsum("bhkv,bhk->bhv", state, k[:, i]))
            state = state + torch.einsum("bhk,bhv->bhkv", k[:, i], update)
            expected.append(torch.einsum("bhkv,bhk->bhv", state, q[:, i]))
        torch.testing.assert_close(actual, torch.stack(expected, 1), atol=1e-6, rtol=1e-5)

    def test_official_nearest_training_grid_schedule(self):
        # Official MOSS V2 scheduler produces [1, .024, 0] at two steps,
        # unlike a plain shifted linspace schedule.
        torch.testing.assert_close(sampling_sigmas(2, 5), torch.tensor([1., .024, 0.]), atol=1e-7, rtol=0)
        sigmas = sampling_sigmas(50, 5)
        self.assertEqual(sigmas[0].item(), 1)
        self.assertEqual(sigmas[-1].item(), 0)
        self.assertTrue(torch.all(sigmas[:-1] > sigmas[1:]))
        torch.testing.assert_close(sigmas[:-1] * 1000, (sigmas[:-1] * 1000).round(), atol=1e-4, rtol=0)
        for steps, shift in [(0, 5), (2, 0), (2, float("nan"))]:
            with self.assertRaises(ValueError):
                sampling_sigmas(steps, shift)

    def test_dit_mask_and_negative_branch_skipping(self):
        torch.manual_seed(2)
        model = MOSSImageDiT(dim=32, ffn_dim=64, num_heads=2, num_layers=2,
                             text_dim=16, freq_dim=8, latent_channels=4).eval()
        x, text = torch.randn(1, 4, 2, 3), torch.randn(1, 5, 16)
        mask = torch.tensor([[1, 1, 1, 0, 0]])
        with torch.no_grad():
            result = model(x, 500, text, mask)
            text[:, 3:] = 1e6
            torch.testing.assert_close(result, model(x, 500, text, mask))
            self.assertFalse(torch.allclose(result, model(x, 500, text, mask, skip_layers=(1,))))
        with self.assertRaises(ValueError):
            model(x, 500, text, mask, skip_layers=(22,))

    def test_flux2_vae_matches_diffusers_decode_with_latent_normalization(self):
        from backend.diffusers_compat import preload_attention_dispatch_for_torch_24
        preload_attention_dispatch_for_torch_24()
        from diffusers import AutoencoderKLFlux2

        options = dict(block_out_channels=(32, 32, 32, 32),
                       decoder_block_out_channels=(32, 32, 32, 32), latent_channels=2, layers_per_block=1)
        model, reference = Flux2VAE(**options).eval(), AutoencoderKLFlux2(**options).eval()
        with torch.no_grad():
            model.bn.running_mean.fill_(.2)
            model.bn.running_var.fill_(1.5)
            reference.load_state_dict(model.state_dict())
            z = torch.randn(1, 8, 2, 2)
            mean, std = model.latent_stats("cpu", torch.float32)
            unpacked = (z * std + mean).reshape(1, 2, 2, 2, 2, 2).permute(0, 1, 4, 2, 5, 3).reshape(1, 2, 4, 4)
            torch.testing.assert_close(model.decode(z), reference.decode(unpacked).sample, atol=1e-6, rtol=1e-5)

    def test_safe_sharded_loading_rejects_escape_missing_and_unexpected_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_file({"weight": torch.ones(2, 2)}, str(root / "part.safetensors"))
            index = root / "model.safetensors.index.json"
            index.write_text(json.dumps({"weight_map": {"weight": "../escape.safetensors"}}))
            with self.assertRaises(ValueError):
                weight_shards(root, "model")
            index.write_text(json.dumps({"weight_map": {"weight": "part.safetensors"}}))
            with torch.device("meta"):
                model = nn.Linear(2, 2, bias=False)
            load_component(model, root, "model", torch.float32)
            self.assertEqual(model.weight.device.type, "cpu")
            torch.testing.assert_close(model.weight, torch.ones(2, 2))
            with self.assertRaisesRegex(ValueError, "Missing weights"):
                load_component(nn.Linear(2, 2), root, "model", torch.float32)
            index.write_text(json.dumps({"weight_map": {"other": "part.safetensors"}}))
            with self.assertRaisesRegex(ValueError, "do not match"):
                load_component(model, root, "model", torch.float32)
        self.assertEqual(text_weight_key("language_model.norm.weight"), "norm.weight")
        self.assertIsNone(text_weight_key("visual.patch_embed.weight"))

    def test_local_bundle_load_and_generation_without_remote_python(self):
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            te_options = dict(hidden_size=16, intermediate_size=32, num_hidden_layers=4,
                              num_attention_heads=2, num_key_value_heads=1, head_dim=8, vocab_size=32,
                              linear_num_key_heads=1, linear_num_value_heads=2,
                              linear_key_head_dim=4, linear_value_head_dim=4)
            dit_options = dict(dim=32, ffn_dim=64, num_heads=2, num_layers=2, text_dim=16,
                               freq_dim=8, latent_channels=8)
            vae_options = dict(block_out_channels=(32, 32, 32, 32), decoder_block_out_channels=(32, 32, 32, 32),
                               latent_channels=2, layers_per_block=1)
            components = [
                ("transformer", "diffusion_pytorch_model", MOSSImageDiT(**dit_options),
                 dict(_class_name="MOSSImageTransformer", **dit_options)),
                ("text_encoder", "model", TextEncoder(te_options), dict(model_type="qwen3_5", text_config=te_options)),
                ("vae", "diffusion_pytorch_model", Flux2VAE(**vae_options), dict(_class_name="AutoencoderKLFlux2", **vae_options)),
            ]
            for directory, stem, model, config in components:
                folder = root / directory
                folder.mkdir()
                (folder / "config.json").write_text(json.dumps(config))
                state = model.state_dict()
                if directory == "text_encoder":
                    state = {"language_model." + k: v for k, v in state.items()}
                    state["visual.unused"] = torch.ones(1)
                save_file(state, str(folder / f"{stem}.safetensors"))
            (root / "tokenizer").mkdir()
            Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]")).save(str(root / "tokenizer/tokenizer.json"))
            # A downloaded Python file must never be imported by the loader.
            (root / "pipeline_moss_image.py").write_text("raise RuntimeError('remote code executed')")
            pipe = MOSSPipeline.from_pretrained(str(root))
            image = pipe("a cat", width=32, height=32, steps=2, seed=9, uncond_skip_layers=())
            again = pipe("a cat", width=32, height=32, steps=2, seed=9, uncond_skip_layers=())
            self.assertEqual(image.size, (32, 32))
            self.assertEqual(image.tobytes(), again.tobytes())
            self.assertEqual(next(pipe.vae.parameters()).dtype, torch.float32)
            with patch.object(pipe.vae, "decode", side_effect=RuntimeError("decode failed")):
                with self.assertRaisesRegex(RuntimeError, "decode failed"):
                    pipe("a cat", width=32, height=32, steps=1, uncond_skip_layers=())
            for model in (pipe.transformer, pipe.text_encoder, pipe.vae):
                self.assertEqual(next(model.parameters()).device.type, "cpu")
            with self.assertRaises(ValueError):
                pipe("a cat", width=31, height=32, steps=1, uncond_skip_layers=())
        self.assertEqual(format_prompt("你好"), "<|im_start|>user\n你好<|im_end|>\n<|im_start|>assistant\n<think>\n")


if __name__ == "__main__":
    unittest.main()
