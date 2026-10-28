"""Local Wan 2.1 T2V-1.3B weights with file-backed CPU loading."""
import os
from pathlib import Path
import torch
from diffsynth import ModelManager
from diffsynth.models.wan_video_dit import WanModel
from diffsynth.models.wan_video_text_encoder import WanTextEncoder
from diffsynth.models.wan_video_vae import WanVideoVAE
from diffsynth.models.utils import load_state_dict_from_safetensors
from ._runtime import wan_runtime
from .Wan2 import Wan2T2VModel, Wan2TextToVideo
from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch


class Wan21T2V13BModel(Wan2T2VModel):
    @staticmethod
    def load_local(model_dir=None):
        root = Path(model_dir or os.environ.get("SSUI_WAN21_MODEL_DIR", "models/wan-mac"))
        entries = (
            ("diffusion_pytorch_model.safetensors", "wan_video_dit", WanModel),
            ("models_t5_umt5-xxl-enc-bf16.pth", "wan_video_text_encoder", WanTextEncoder),
            ("Wan2.1_VAE.pth", "wan_video_vae", WanVideoVAE),
        )
        for filename, _, _ in entries:
            if not (root / filename).is_file():
                raise FileNotFoundError(f"Missing Wan checkpoint: {root / filename}. Run yarn test:wan:smoke --download-only first.")
        if not (root / "google/umt5-xxl/tokenizer_config.json").is_file():
            raise FileNotFoundError(f"Missing Wan tokenizer: {root / 'google/umt5-xxl'}")
        manager = ModelManager(device="cpu", torch_dtype=wan_runtime()["torch_dtype"])
        for filename, name, cls in entries:
            path = str(root / filename)
            if filename.endswith(".safetensors"):
                weights = load_state_dict_from_safetensors(path, torch_dtype=manager.torch_dtype)
                _, config = WanModel.state_dict_converter().from_civitai(weights)
                if config.get("dim") != 1536 or config.get("num_layers") != 30 or config.get("in_dim", 16) != 16:
                    raise ValueError("Expected Wan 2.1 T2V-1.3B checkpoint")
            else:
                weights = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
            manager.load_model_from_single_file(path, state_dict=weights, model_names=[name],
                                                model_classes=[cls], model_resource="civitai")
            del weights
        return Wan21T2V13BModel(manager)


@param("seed", Random(), default=42)
@param("num_frames", Slider(5, 81, 4), default=17)
@param("num_inference_steps", Slider(2, 100, 1), default=30)
@param("cfg_scale", Slider(1, 10, 0.1), default=5)
@param("height", Slider(64, 1280, 16), default=512)
@param("width", Slider(64, 1280, 16), default=512)
@param("tiled", Switch(), default=True)
def Wan21TextToVideo(config: SSUIConfig, base_model: Wan21T2V13BModel,
                     prompt: Prompt, negative_prompt: Prompt) -> list[Image]:
    return Wan2TextToVideo(config, base_model, prompt, negative_prompt)
