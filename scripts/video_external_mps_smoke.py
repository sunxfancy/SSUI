"""Weight-free tests of the pinned external H3/LTX stack on real MPS."""
import os
# Unsupported accelerator operators must fail instead of silently running on CPU.
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"

import copy
import tempfile
from pathlib import Path
import sys
import torch


def test_ltx_embedding_offload(dtype=torch.float32):
    cpu_tolerance = 0.02 if dtype == torch.bfloat16 else 0.005
    from types import SimpleNamespace
    from transformers import Gemma4UnifiedConfig, Gemma4UnifiedTextConfig, Gemma4UnifiedForConditionalGeneration
    from ltx_core.text_encoders.gemma.encoders.base_encoder import LTXGemmaTextEncoder
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions/Video/ssui_video"))
    from ltx_runner import _offload_gemma_embedding
    config = Gemma4UnifiedConfig(text_config=Gemma4UnifiedTextConfig(
        vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
        num_attention_heads=2, num_key_value_heads=1, head_dim=16, global_head_dim=16,
        layer_types=["sliding_attention", "full_attention"], sliding_window=16))
    model = Gemma4UnifiedForConditionalGeneration(config).to(dtype=dtype).eval()
    tokenizer = SimpleNamespace(tokenize_with_weights=lambda text: {
        "gemma": [(2, 1), (3 if text == "a" else 5, 1), (4, 1), (0, 0)]})
    encoder = LTXGemmaTextEncoder(model=model, tokenizer=tokenizer)
    with torch.inference_mode():
        expected = encoder.encode(["a", "b"])
        encoder.to("mps")
        baseline = encoder.encode(["a", "b"])
        _offload_gemma_embedding(encoder)
        embedding = encoder.model.model.language_model.embed_tokens
        assert embedding.weight.device.type == "meta"
        assert encoder.model.lm_head.weight.device.type == "cpu"
        for _ in range(2):
            actual = encoder.encode(["a", "b"])
            assert embedding.weight.device.type == "meta", "Embedding retained on GPU after lookup"
            for (states, mask), (cpu_states, cpu_mask), (gpu_states, _) in zip(actual, expected, baseline):
                torch.testing.assert_close(mask.cpu(), cpu_mask)
                for state, cpu_state, gpu_state in zip(states, cpu_states, gpu_states):
                    assert state.device.type == "mps"
                    torch.testing.assert_close(gpu_state.cpu(), cpu_state, atol=cpu_tolerance, rtol=cpu_tolerance)
                    torch.testing.assert_close(state.cpu(), cpu_state, atol=cpu_tolerance, rtol=cpu_tolerance)
                    torch.testing.assert_close(state, gpu_state, atol=0.005, rtol=0.005)
        assert encoder.encode([]) == []
        encoder.dispose()
        assert not hasattr(embedding, "_hf_hook")
        assert encoder.model.lm_head.weight.device.type == "meta"
    from ltx_core.text_encoders.gemma.feature_extractor import FeatureExtractorV2
    from ltx_runner import _build_mps_embeddings_processor
    from unittest.mock import MagicMock
    feature = FeatureExtractorV2(torch.nn.Linear(96, 16), 32, torch.nn.Linear(96, 8)).to(dtype=dtype).eval()
    hidden = tuple(torch.randn(2, 137, 32, dtype=dtype) for _ in range(3))
    mask = torch.ones(2, 137, dtype=torch.long)
    mask[0, 110:] = 0
    mask[1, :5] = 0
    with torch.inference_mode():
        reference = feature(hidden, mask)
        builder = MagicMock()
        builder.build.return_value = feature
        feature = _build_mps_embeddings_processor(SimpleNamespace(
            _embeddings_processor_builder=builder, _dtype=dtype))
        actual = feature(tuple(h.to("mps") for h in hidden), mask.to("mps"))
        for output, expected in zip(actual, reference):
            assert output.device.type == "mps"
            torch.testing.assert_close(output.cpu(), expected, atol=cpu_tolerance, rtol=cpu_tolerance)
        feature.dispose()
        assert all(p.device.type == "meta" for p in feature.parameters())
    print("LTX V2 video/audio feature projection sequential MPS offload: PASS", flush=True)
    print("LTX Gemma embedding offload + no KV cache, repeated batched MPS/CPU equivalence: PASS", flush=True)


def test_ltx_streaming_filter():
    from safetensors.torch import save_file
    from ltx_core.block_streaming import StreamingModelBuilder
    from ltx_core.loader.sd_ops import SDOps
    from ltx_core.model.disposable import Disposable
    from ltx_pipelines.utils.streaming_model import streaming_model
    from ltx_runner import _bounded_disk_streaming

    class Tiny(torch.nn.Module, Disposable):
        def __init__(self):
            super().__init__()
            self.projection = torch.nn.Linear(4, 4)
            self.blocks = torch.nn.ModuleList([torch.nn.Linear(4, 4) for _ in range(2)])
        def forward(self, x):
            x = self.projection(x)
            for block in self.blocks:
                x = torch.tanh(block(x))
            return x
    class Configurator:
        @classmethod
        def from_metadata(cls, metadata):
            return Tiny()

    reference = Tiny().eval()
    inputs = [torch.randn(2, 4), torch.randn(3, 4)]
    with tempfile.TemporaryDirectory() as directory, torch.inference_mode():
        checkpoint = str(Path(directory) / "model.safetensors")
        save_file({**reference.state_dict(), "unused_connector.weight": torch.randn(8, 8)},
                  checkpoint, metadata={"config": "{}"})
        builder = StreamingModelBuilder(model_path=checkpoint, model_class_configurator=Configurator,
            model_sd_ops=SDOps("tiny").with_matching(), blocks_attr="blocks", blocks_prefix="blocks")
        with _bounded_disk_streaming(), streaming_model(builder, torch.device("mps"), torch.float32) as model:
            for x in inputs:
                actual = model(x.to("mps"))
                assert actual.device.type == "mps"
                torch.testing.assert_close(actual.cpu(), reference(x), atol=0.0001, rtol=0.0001)
    print("LTX single-slot disk streaming + unused weight filtering, repeated CPU/MPS equivalence: PASS", flush=True)


def main():
    if not torch.backends.mps.is_available():
        raise RuntimeError("These tests require real MPS; CPU fallback is not allowed")
    torch.manual_seed(7)
    if "--ltx-memory-only" in sys.argv:
        for dtype in (torch.float32, torch.bfloat16):
            print(f"LTX memory test dtype: {dtype}", flush=True)
            test_ltx_embedding_offload(dtype)
        test_ltx_streaming_filter()
        return
    from diffusers import MiniMaxH3Transformer3DModel
    from accelerate import cpu_offload
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions/Video/ssui_video"))
    from h3_runner import _checkpoint_offload
    from ltx_core.model.transformer.attention import MPSSdpaAttention, PytorchAttention

    model = MiniMaxH3Transformer3DModel(
        num_attention_heads=2, attention_head_dim=16, hidden_size=24,
        num_layers=2, num_refiner_layers=2, ffn_dim=32, in_channels=4,
        audio_in_channels=6, patch_size=(1, 2, 2), text_dim=8, freq_dim=8,
        time_embed_hidden_dim=24, time_embed_dim=16, rope_freq_dim=2,
    ).eval()
    inputs = dict(
        hidden_states=torch.randn(1, 8, 16), audio_hidden_states=torch.randn(1, 6, 6),
        encoder_hidden_states=torch.randn(1, 4, 8), timestep=torch.tensor([0.7, 0.3]),
        timestep_indices=torch.tensor([0]*4 + [1]*6 + [0]*8),
        token_tags=torch.tensor([1]*4 + [2]*6 + [0]*8),
        position_ids=torch.arange(18).float()[:, None].expand(-1, 3).clone(),
        text_indices=torch.arange(4), audio_indices=torch.arange(4, 10),
        video_indices=torch.arange(10, 18), return_dict=False,
    )
    with torch.inference_mode():
        expected = model(**inputs)
        gpu = copy.deepcopy(model)
        cpu_offload(gpu, execution_device=torch.device("mps"), offload_buffers=True)
        actual = gpu(**{k: v.to("mps") if isinstance(v, torch.Tensor) else v for k, v in inputs.items()})
        for result, reference in zip(actual, expected):
            assert result.device.type == "mps"
            torch.testing.assert_close(result.cpu(), reference, atol=0.005, rtol=0.005)
        print("H3 joint audio/video DiT + MPS sequential offload: PASS", flush=True)
        # Exercise the checkpoint loader's mixed BF16/FP32 policy used by H3.
        with tempfile.TemporaryDirectory() as directory:
            model.save_pretrained(directory)
            mixed = MiniMaxH3Transformer3DModel.from_pretrained(directory, dtype=torch.bfloat16).eval()
            mixed_inputs = {k: v.to(torch.bfloat16) if isinstance(v, torch.Tensor) and v.is_floating_point()
                            and k.endswith("hidden_states") else v for k, v in inputs.items()}
            expected = mixed(**mixed_inputs)
            _checkpoint_offload(mixed, directory)
            actual = mixed(**{k: v.to("mps") if isinstance(v, torch.Tensor) else v for k, v in mixed_inputs.items()})
        for result, reference in zip(actual, expected):
            assert result.device.type == "mps"
            torch.testing.assert_close(result.cpu(), reference, atol=0.02, rtol=0.02)
        print("H3 checkpoint mixed BF16/FP32 + MPS disk streaming: PASS", flush=True)
        from diffusers import AutoencoderKLMiniMaxH3
        vae = AutoencoderKLMiniMaxH3(in_channels=3, out_channels=3, latent_channels=4,
            block_out_channels=(8,16), layers_per_block=1, spatial_downsample_factors=(2,2),
            temporal_downsample_factors=(2,2), norm_num_groups=8, decoder_num_layers=2,
            decoder_num_attention_heads=2, decoder_attention_head_dim=8,
            decoder_num_register_tokens=2, decoder_ffn_mult=2, clip_length=17, token_drop=3,
            latents_mean=(0.0,)*4, latents_std=(1.0,)*4).eval()
        pixels = torch.randn(1, 3, 22, 8, 8)
        expected_latents = vae.encode(pixels).latent_dist.mode()
        expected = vae.decode(expected_latents).sample
        cpu_offload(vae, execution_device=torch.device("mps"), offload_buffers=True)
        actual_latents = vae.encode(pixels.to("mps")).latent_dist.mode()
        torch.testing.assert_close(actual_latents.cpu(), expected_latents, atol=0.01, rtol=0.01)
        actual = vae.decode(actual_latents).sample
        assert actual.device.type == "mps"
        torch.testing.assert_close(actual.cpu(), expected, atol=0.01, rtol=0.01)
        print("H3 complete tiny video VAE + MPS sequential offload: PASS", flush=True)

        from diffusers import AutoencoderKLMiniMaxH3Audio
        audio_vae = AutoencoderKLMiniMaxH3Audio(
            encoder_dim=4, encoder_rates=(2, 2), latent_dim=32, latent_channels=8,
            num_attention_heads=2, decoder_dim=16, decoder_rates=(2, 2),
            decoder_kernel_sizes=(4, 4), resblock_kernel_sizes=(3, 7),
            resblock_dilation_sizes=((1, 3), (1, 3)), sampling_rate=32000,
            latents_mean=[0.0]*8, latents_std=[1.0]*8).eval()
        waveform = torch.randn(2, 1, 32)
        expected = audio_vae(waveform).sample
        audio_vae.to("mps")
        actual = audio_vae(waveform.to("mps")).sample
        assert actual.device.type == "mps"
        torch.testing.assert_close(actual.cpu(), expected, atol=0.01, rtol=0.01)
        print("H3 complete tiny audio VAE on MPS: PASS", flush=True)

        q, k, v = (torch.randn(1, 16, 128) for _ in range(3))
        expected = PytorchAttention()(q, k, v, heads=2)
        actual = MPSSdpaAttention()(q.to("mps"), k.to("mps"), v.to("mps"), heads=2)
        assert actual.device.type == "mps"
        torch.testing.assert_close(actual.cpu(), expected, atol=0.005, rtol=0.005)
        print("LTX Apple fused MPS attention: PASS", flush=True)
        from ltx_core.model.transformer.model import LTXModel, LTXModelType
        from ltx_core.model.transformer.modality import Modality, TokenTimesteps
        from ltx_core.model.transformer.attention import AttentionOps
        ltx = LTXModel(model_type=LTXModelType.VideoOnly, num_attention_heads=2,
                       attention_head_dim=64, in_channels=8, out_channels=8,
                       num_layers=1, cross_attention_dim=128,
                       attention_ops=AttentionOps(attention_function=PytorchAttention()),
                       use_middle_indices_grid=False, positional_embedding_max_pos=[20,20,20]).eval()
        # Upstream expects checkpoint loading; some AdaLN tables use torch.empty.
        for parameter in ltx.parameters():
            parameter.normal_(mean=0.0, std=0.02)
        def modality(device):
            return Modality(latent=latent.to(device), sigma=torch.ones(1, device=device),
                            timesteps=TokenTimesteps(torch.ones(1, 8, device=device)),
                            positions=torch.zeros(1, 3, 8, device=device), context=context.to(device))
        latent, context = torch.randn(1, 8, 8), torch.randn(1, 4, 128)
        expected = ltx(video=modality("cpu"), audio=None, perturbations=None)[0]
        ltx.to("mps")
        actual = ltx(video=modality("mps"), audio=None, perturbations=None)[0]
        assert actual.device.type == "mps"
        torch.testing.assert_close(actual.cpu(), expected, atol=0.005, rtol=0.005)
        print("LTX complete tiny video DiT: PASS", flush=True)



if __name__ == "__main__":
    main()
