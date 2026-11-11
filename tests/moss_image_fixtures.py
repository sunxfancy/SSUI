"""Deterministic, small real safetensors bundles for offline MOSS integration tests."""
import json
from pathlib import Path

import torch
from safetensors.torch import save_file
from tokenizers import Tokenizer
from tokenizers.models import WordLevel

from backend.moss_image.dit import MOSSImageDiT
from backend.moss_image.text_encoder import TextEncoder
from backend.moss_image.vae import Flux2VAE


def create_moss_bundle(root, dit_layers=24, sharded=True):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    text = dict(hidden_size=16, intermediate_size=32, num_hidden_layers=4,
                num_attention_heads=2, num_key_value_heads=1, head_dim=8, vocab_size=32,
                linear_num_key_heads=1, linear_num_value_heads=2,
                linear_key_head_dim=4, linear_value_head_dim=4)
    dit = dict(dim=32, ffn_dim=64, num_heads=2, num_layers=dit_layers,
               text_dim=16, freq_dim=8, latent_channels=8)
    vae = dict(block_out_channels=(32, 32, 32, 32), decoder_block_out_channels=(32, 32, 32, 32),
               latent_channels=2, layers_per_block=1)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(23)
        components = [
            ("transformer", "diffusion_pytorch_model", MOSSImageDiT(**dit), dict(_class_name="MOSSImageTransformer", **dit)),
            ("text_encoder", "model", TextEncoder(text), dict(model_type="qwen3_5", text_config=text)),
            ("vae", "diffusion_pytorch_model", Flux2VAE(**vae), dict(_class_name="AutoencoderKLFlux2", **vae)),
        ]
    for directory, stem, model, config in components:
        folder = root / directory
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        state = model.state_dict()
        if directory == "text_encoder":
            state = {"language_model." + key: value for key, value in state.items()}
            state["visual.unused"] = torch.ones(1)
        if sharded:
            mapping = {}
            items = list(state.items())
            for shard in range(2):
                name = f"{stem}-{shard + 1:05d}-of-00002.safetensors"
                values = dict(items[shard::2])
                save_file(values, str(folder / name))
                mapping.update({key: name for key in values})
            (folder / f"{stem}.safetensors.index.json").write_text(json.dumps({"weight_map": mapping}), encoding="utf-8")
        else:
            save_file(state, str(folder / f"{stem}.safetensors"))
    (root / "tokenizer").mkdir()
    Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]")).save(str(root / "tokenizer/tokenizer.json"))
    (root / "scheduler").mkdir()
    (root / "scheduler/scheduler_config.json").write_text(json.dumps({
        "_class_name": "MOSSImageScheduler", "num_train_timesteps": 1000, "training_shift": 1., "shift": 5.,
    }), encoding="utf-8")
    (root / "pipeline_moss_image.py").write_text("raise RuntimeError('remote code executed')\n", encoding="utf-8")
    return root
