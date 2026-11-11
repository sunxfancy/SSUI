"""Real Diffusers/PEFT integration with a tiny random FLUX.2 transformer."""
from pathlib import Path
import unittest
import uuid

import torch
from safetensors.torch import save_file
from backend.lora import apply_diffusers_lora


class DiffusersLoraTests(unittest.TestCase):
    def test_flux2_checkpoint_load_and_scaled_inference(self):
        from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel
        transformer = Flux2Transformer2DModel(
            in_channels=4, num_layers=1, num_single_layers=1,
            attention_head_dim=8, num_attention_heads=1, joint_attention_dim=8,
            timestep_guidance_channels=8, axes_dims_rope=(2, 2, 2, 2))
        pipe = Flux2KleinPipeline(None, None, None, None, transformer)
        directory = Path(__file__).resolve().parents[1] / "build" / ("lora-peft-" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        self.addCleanup(directory.rmdir)
        path = directory / "adapter.safetensors"
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        save_file({"transformer.x_embedder.lora_A.weight": torch.ones(1, 4),
                   "transformer.x_embedder.lora_B.weight": torch.ones(8, 1)}, str(path))
        sample = torch.ones(1, 4)
        before = transformer.x_embedder(sample).detach()
        apply_diffusers_lora(pipe, str(path), 0.5)
        torch.testing.assert_close(transformer.x_embedder(sample), before + 2)
        pipe.set_adapters(["ssui"], adapter_weights=[-0.25])
        torch.testing.assert_close(transformer.x_embedder(sample), before - 1)
