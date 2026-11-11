"""Opt-in, weight-free checks against installed video dependencies (no stubs)."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(os.environ.get("SSUI_RUN_VIDEO_RUNTIME_TESTS") == "1",
                     "requires installed Mac/video runtime dependencies")
class VideoRuntimeTest(unittest.TestCase):
    def test_real_imports_operators_and_video_encoding(self):
        root = Path(__file__).resolve().parents[1]
        # A subprocess prevents the existing diffsynth_test stubs from masking failures.
        code = r'''
import importlib
from unittest.mock import patch
import tempfile
from pathlib import Path
import imageio.v2 as imageio
import numpy as np
import torch
import mediapipe
import diffsynth
from diffsynth.pipelines.base import BasePipeline
from diffsynth.vram_management.layers import WanAutoCastLayerNorm
from diffsynth.vram_management.layers import AutoWrappedEmbedding
# Offloading must not duplicate the large embedding on CPU or mutate its source.
embedding = torch.nn.Embedding(32, 8, padding_idx=0, max_norm=1.0)
source = embedding.weight.detach().clone()
reference = torch.nn.Embedding(32, 8, padding_idx=0, max_norm=1.0).double()
reference.load_state_dict(embedding.state_dict())
ids = torch.tensor([[0, 1, 7, 1]])
wrapped_embedding = AutoWrappedEmbedding(embedding, torch.float32, "cpu", torch.float32,
                                         "cpu", torch.float64, "cpu", None)
with patch("diffsynth.vram_management.layers.copy.deepcopy", side_effect=AssertionError("CPU clone")):
    torch.testing.assert_close(wrapped_embedding(ids), reference(ids))
    torch.testing.assert_close(wrapped_embedding(ids), reference(ids))
torch.testing.assert_close(embedding.weight, source)
# CPU offload must normalize BF16 affine parameters with FP32 activations.
layer = torch.nn.LayerNorm(8).to(torch.bfloat16)
x = torch.randn(2, 4, 8, dtype=torch.bfloat16)
wrapped = WanAutoCastLayerNorm(layer, torch.bfloat16, "cpu", torch.bfloat16, "cpu",
                               torch.bfloat16, "cpu", None)
expected = torch.nn.functional.layer_norm(x.float(), (8,), layer.weight.float(), layer.bias.float(), layer.eps).to(x.dtype)
torch.testing.assert_close(wrapped(x), expected)
from diffsynth.models.cog_dit import CogPatchify
from diffsynth.models.attention import Attention
from diffsynth.models.wan_video_dit import WanModel, rope_apply, precompute_freqs_cis, prepare_rope_freqs
from diffsynth.pipelines.wan_video_new import WanVideoPipeline
from diffsynth.models.qwen_image_text_encoder import QwenImageTextEncoder
import transformers
from diffsynth.pipelines.wan_video import model_fn_wan_video

assert Path(diffsynth.__file__).resolve().is_relative_to(Path("extensions/Video").resolve())
for name in ("AnimateDiff", "CogVideo", "Hunyuan", "Wan", "Wan2", "Wan22"):
    importlib.import_module("ssui_video." + name)
# Keep checkpoint loading on CPU before pipeline offloading, without downloads.
for module_name, classes in (("Wan", ("WanVideoModel",)),
                             ("Wan2", ("Wan2T2VModel", "Wan2I2VModel"))):
    module = importlib.import_module("ssui_video." + module_name)
    for cls in classes:
        with patch.object(module, "ModelManager") as manager, patch.object(module, "snapshot_download"):
            getattr(module, cls).load()
            assert manager.call_args.kwargs["device"] == "cpu"
            assert manager.call_args.kwargs["torch_dtype"] == module.wan_runtime()["torch_dtype"]
            assert manager.return_value.load_models.call_args.kwargs.get("device", "cpu") == "cpu"
wan22 = importlib.import_module("ssui_video.Wan22")
for cls in ("Wan22TI2VModel", "Wan22T2VA14BModel", "Wan22I2VA14BModel"):
    with patch.object(wan22.WanVideoPipeline, "from_pretrained") as factory:
        getattr(wan22, cls).load()
        kwargs = factory.call_args.kwargs
        assert kwargs["device"] == wan22.wan_runtime()["device"]
        assert kwargs["torch_dtype"] == wan22.wan_runtime()["torch_dtype"]
        assert all(c.offload_device == "cpu" for c in kwargs["model_configs"])
        factory.return_value.enable_vram_management.assert_called_once()
if not hasattr(transformers, "Qwen2_5_VLModel"):
    try:
        QwenImageTextEncoder()
    except ImportError as exc:
        assert "Qwen2.5-VL" in str(exc)
    else:
        raise AssertionError("missing optional encoder dependency was not reported")

from ss_executor.loader import SSLoader
loader = SSLoader()
loader.load("examples/advance/workflow-video-mac.py")
loader.Execute()
workflow_config = loader.GetConfig("txt2vid_animatediff")
assert "Generate Video" in workflow_config
assert "seed" in workflow_config["Generate Video"]
assert workflow_config["Generate Video"]["width"]["default"] == 256
assert workflow_config["Generate Video"]["num_frames"]["default"] == 8

# Preparing the real Wan sandbox must not download or load multi-GB weights.
from ssui_video.Wan21 import Wan21T2V13BModel, Wan21TextToVideo
with patch.object(Wan21T2V13BModel, "load_local", side_effect=AssertionError("prepare loaded weights")):
    wan_loader = SSLoader()
    wan_loader.load("examples/advance/workflow-video-wan21.py")
    wan_loader.Execute()
    wan_config = wan_loader.GetConfig("txt2vid_wan21_13b")["Generate Video"]
    assert wan_config["width"]["default"] == 512
    assert wan_config["num_frames"]["default"] == 17
    assert wan_config["num_inference_steps"]["default"] == 30

from ssui.config import SSUIConfig
from ssui.base import Prompt
config = SSUIConfig()("wan21_test")
for key, value in dict(width=256, height=256, num_frames=9, num_inference_steps=4,
                       cfg_scale=3.5, seed=123, tiled=False).items():
    config[key] = value
with patch("ssui_video.Wan2.WanVideoPipeline.from_model_manager") as factory:
    factory.return_value.return_value = []
    Wan21TextToVideo(config, Wan21T2V13BModel(object()), Prompt("cat"), Prompt("blur"))
    actual = factory.return_value.call_args.kwargs
    assert actual["num_frames"] == 9 and actual["num_inference_steps"] == 4
    assert actual["cfg_scale"] == 3.5 and actual["seed"] == 123
with tempfile.TemporaryDirectory() as directory:
    with patch("ssui_video.Wan21.ModelManager", side_effect=AssertionError("allocated before preflight")):
        try:
            Wan21T2V13BModel.load_local(directory)
        except FileNotFoundError as exc:
            assert "Missing Wan checkpoint" in str(exc)
        else:
            raise AssertionError("missing model accepted")

device = "mps" if torch.backends.mps.is_available() else "cpu"
print("Runtime device:", device, "torch:", torch.__version__, flush=True)
noise_pipe = BasePipeline(device=device)
noise = noise_pipe.generate_noise((1, 4, 8, 8), seed=42, device=device)
repeat = noise_pipe.generate_noise((1, 4, 8, 8), seed=42, device=device)
assert noise.device.type == device
torch.testing.assert_close(noise, repeat)
assert not torch.equal(noise, noise_pipe.generate_noise((1, 4, 8, 8), seed=43, device=device))
torch.manual_seed(42)
with torch.no_grad():
    dtype = torch.float16 if device == "mps" else torch.float32
    attention = Attention(8, 2, 4).to(device=device, dtype=dtype)
    output = attention(torch.randn(1, 4, 8, device=device, dtype=dtype))
    assert output.shape == (1, 4, 8) and torch.isfinite(output).all()
    patchify = CogPatchify(2, 8, 2).to(device=device, dtype=dtype)
    output = patchify(torch.randn(1, 2, 2, 4, 4, device=device, dtype=dtype))
    assert output.shape == (1, 8, 8) and torch.isfinite(output).all()
    # Compare the real-valued MPS RoPE implementation to the original complex one.
    x = torch.randn(2, 5, 24)
    freqs = precompute_freqs_cis(12, end=5).unsqueeze(1)
    reference = rope_apply(x, freqs, 2)
    pairs = torch.view_as_real(freqs).float().to(device)
    actual = rope_apply(x.to(device), pairs, 2).cpu()
    torch.testing.assert_close(actual, reference, rtol=1e-5, atol=1e-6)
    # Exercise an entire small randomly initialized Wan transformer, no weights/download.
    model = WanModel(dim=24, in_dim=2, ffn_dim=48, out_dim=2, text_dim=8,
                     freq_dim=8, eps=1e-6, patch_size=(1, 2, 2), num_heads=2,
                     num_layers=1, has_image_input=False).eval()
    latent = torch.randn(1, 2, 2, 4, 4)
    timestep = torch.tensor([500.0])
    context = torch.randn(1, 3, 8)
    expected = model(latent, timestep, context)
    actual = model.to(device)(latent.to(device), timestep.to(device), context.to(device)).cpu()
    torch.testing.assert_close(actual, expected, rtol=2e-3, atol=2e-4)
    pipeline_output = model_fn_wan_video(model, x=latent.to(device),
                                       timestep=timestep.to(device), context=context.to(device)).cpu()
    torch.testing.assert_close(pipeline_output, actual, rtol=1e-5, atol=1e-6)
    # New Wan 2.2 execution path and actual layer offloading must avoid CUDA.
    import copy
    from diffsynth.pipelines.wan_video_new import model_fn_wan_video as model_fn_new
    from diffsynth.device_utils import device_memory
    from ssui_video._runtime import wan_runtime
    wan_dtype = wan_runtime()["torch_dtype"]
    base = model.cpu().to(wan_dtype)
    inputs = {"latents": latent.to(device=device, dtype=wan_dtype),
              "timestep": timestep.to(device=device, dtype=wan_dtype),
              "context": context.to(device=device, dtype=wan_dtype)}
    reference = model_fn_new(base, latents=latent.to(wan_dtype),
                             timestep=timestep.to(wan_dtype), context=context.to(wan_dtype))
    with patch("torch.cuda.mem_get_info", side_effect=AssertionError("CUDA memory queried")), \
         patch("torch.cuda.empty_cache", side_effect=AssertionError("CUDA cache touched")):
        assert device_memory(device)[0] > 0
        for limit in (0.0, 1.0):
            pipe = WanVideoPipeline(device=device, torch_dtype=wan_dtype)
            pipe.dit = copy.deepcopy(base)
            pipe.enable_vram_management(vram_limit=limit, vram_buffer=0)
            pipe.load_models_to_device(["dit"])
            actual = model_fn_new(pipe.dit, **inputs).cpu()
            torch.testing.assert_close(actual.float(), reference.float(), rtol=0.05, atol=0.05)
            pipe.load_models_to_device([])
            assert all(p.device.type == "cpu" for p in pipe.dit.parameters())
            seeded = pipe.generate_noise((1, 2, 2, 4, 4), seed=7, rand_device=device)
            torch.testing.assert_close(seeded, pipe.generate_noise((1, 2, 2, 4, 4), seed=7, rand_device=device))
        print("Wan 2.2 BF16/FP32 forward, memory budget and layer offloading passed:", wan_dtype)
from diffsynth.models.cog_dit import CogDiT
from diffsynth.pipelines.cog_video import CogVideoPipeline
if torch.backends.mps.is_available():
    cog = CogDiT(dim=128, text_dim=32, time_dim=64, num_heads=2, num_layers=1).eval()
    inputs = dict(hidden_states=torch.randn(1, 16, 2, 4, 4), timestep=torch.ones(1), prompt_emb=torch.randn(1, 8, 32))
    with torch.inference_mode():
        reference = cog(**inputs)
        pipe = CogVideoPipeline(device="mps", torch_dtype=torch.float32)
        pipe.dit = cog
        pipe.enable_vram_management()
        pipe.load_models_to_device(["dit"])
        inputs = {k: v.to("mps") for k, v in inputs.items()}
        actual = cog(**inputs)
        torch.testing.assert_close(actual.cpu(), reference, atol=0.002, rtol=0.002)
        tiled = cog(**inputs, tiled=True, tile_size=(4, 4), tile_stride=(4, 4))
        torch.testing.assert_close(tiled.cpu(), actual.cpu(), atol=0.002, rtol=0.002)
        assert actual.device.type == tiled.device.type == "mps"
        assert all(p.device.type == "cpu" for p in cog.parameters())
    print("CogVideo complete tiny DiT, tiled MPS computation and CPU weight offload passed")

# Real Hunyuan layers: CPU-held weights, MPS computations, no CUDA calls.
from diffsynth.models.hunyuan_video_dit import HunyuanVideoDiT, IndividualTokenRefinerBlock
from diffsynth.models.sd3_dit import RMSNorm
from diffsynth.pipelines.hunyuan_video import HunyuanVideoPipeline
if torch.backends.mps.is_available():
    import copy
    for dtype in (torch.float32, torch.bfloat16):
        base = torch.nn.Sequential(torch.nn.Linear(24, 24), RMSNorm(24, eps=1e-6)).eval()
        block = IndividualTokenRefinerBlock(hidden_size=24, num_heads=3).eval()
        x, c = torch.randn(1, 4, 24), torch.randn(1, 24)
        with torch.inference_mode():
            expected = base(x)
            expected_block = block(x, c)
            HunyuanVideoDiT.enable_auto_offload(base, dtype=dtype, device="mps")
            HunyuanVideoDiT.enable_auto_offload(block, dtype=dtype, device="mps")
            with patch("torch.cuda.empty_cache", side_effect=AssertionError("CUDA call")):
                actual = base(x.to("mps", dtype=dtype))
                actual_block = block(x.to("mps", dtype=dtype), c.to("mps", dtype=dtype))
            assert actual.device.type == actual_block.device.type == "mps"
            assert all(p.device.type == "cpu" for p in block.parameters())
            torch.testing.assert_close(actual.cpu().float(), expected, atol=0.05, rtol=0.05)
            torch.testing.assert_close(actual_block.cpu().float(), expected_block, atol=0.05, rtol=0.05)
    from diffsynth.pipelines.hunyuan_video import lets_dance_hunyuan_video
    tiny = HunyuanVideoDiT(hidden_size=96, text_dim=24, num_double_blocks=1, num_single_blocks=1).eval()
    inputs = dict(x=torch.randn(1, 16, 1, 4, 4), t=torch.ones(1),
                  prompt_emb=torch.randn(1, 256, 24), text_mask=torch.ones(1, 256),
                  pooled_prompt_emb=torch.randn(1, 768), guidance=torch.ones(1),
                  freqs_cos=torch.ones(4, 4), freqs_sin=torch.zeros(4, 4))
    with torch.inference_mode():
        expected = lets_dance_hunyuan_video(tiny, **inputs)
        HunyuanVideoDiT.enable_auto_offload(tiny, dtype=torch.bfloat16, device="mps")
        actual = lets_dance_hunyuan_video(tiny, **{k: v.to("mps", dtype=torch.bfloat16) for k, v in inputs.items()})
        assert actual.device.type == "mps"
        torch.testing.assert_close(actual.cpu().float(), expected, atol=0.08, rtol=0.08)
    print("Hunyuan complete tiny DiT denoising forward passed on MPS")
    with HunyuanVideoPipeline(device="mps", torch_dtype=torch.bfloat16).inference_autocast():
        assert (torch.ones(2, device="mps") + 1).device.type == "mps"
    print("Hunyuan token refiner and offloaded Linear/RMSNorm passed on MPS FP32/BF16")
with tempfile.TemporaryDirectory() as checkpoint_dir:
    from diffsynth.models.utils import load_state_dict_from_bin
    for modern in (True, False):
        path = str(Path(checkpoint_dir) / (str(modern) + ".pt"))
        expected = {"weight": torch.randn(3, 4)}
        torch.save(expected, path, _use_new_zipfile_serialization=modern)
        actual = load_state_dict_from_bin(path)
        torch.testing.assert_close(actual["weight"], expected["weight"])

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "smoke.mp4"
    imageio.mimwrite(path, [np.full((16, 16, 3), v, dtype=np.uint8) for v in (0, 128)], fps=2)
    frames = imageio.mimread(path)
    assert len(frames) == 2 and frames[0].shape == (16, 16, 3)
print("Real video imports, attention, Conv3D, Wan RoPE/DiT and FFmpeg round-trip passed.")
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "extensions/Video") + os.pathsep + str(root)
        result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
