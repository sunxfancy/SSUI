"""Exercise real video node loaders without downloading model weights."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import MagicMock, patch

import torch
from backend.util.devices import TorchDevice, TorchDeviceConfig


VIDEO = Path(__file__).resolve().parents[1] / "extensions/Video/ssui_video"


def load_node(name, diffsynth):
    spec = importlib.util.spec_from_file_location("video_device_" + name, VIDEO / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", {"diffsynth": diffsynth}):
        spec.loader.exec_module(module)
    return module


class VideoDeviceTest(unittest.TestCase):
    def stub(self):
        mod = types.ModuleType("diffsynth")
        for name in ("ModelManager", "SDImagePipeline", "SDVideoPipeline",
                     "CogVideoPipeline", "HunyuanVideoPipeline", "download_models",
                     "save_video", "FlowMatchScheduler", "download_customized_models"):
            setattr(mod, name, MagicMock())
        return mod

    def test_loaders_keep_manager_and_weights_on_selected_device(self):
        for node_name, model_name in (("AnimateDiff", "AnimateDiffModel"),
                                      ("CogVideo", "CogVideoModel")):
            for device, dtype in (("cpu", torch.float32), ("mps", torch.float16),
                                  ("cuda:0", torch.float16)):
                with self.subTest(node=node_name, device=device):
                    stub = self.stub()
                    node = load_node(node_name, stub)
                    with patch.object(TorchDevice, "choose_torch_device", return_value=torch.device(device)), \
                         patch.object(TorchDevice, "choose_torch_dtype", return_value=dtype) as precision:
                        model = getattr(node, model_name)
                        result = model() if node_name == "AnimateDiff" else model.load()
                    stub.ModelManager.assert_called_once_with(device=device, torch_dtype=dtype)
                    precision.assert_called_once_with(torch.device(device))
                    self.assertIs(result.model_manager, stub.ModelManager.return_value)
                    # No per-load override may disagree with pipeline manager metadata.
                    self.assertEqual(result.model_manager.load_models.call_args.kwargs, {})

    def test_animatediff_local_weights_skip_download(self):
        stub = self.stub()
        node = load_node("AnimateDiff", stub)
        node.AnimateDiffModel("sd.safetensors", "motion.ckpt")
        stub.download_models.assert_not_called()
        stub.ModelManager.return_value.load_models.assert_called_once_with(["sd.safetensors", "motion.ckpt"])
        with self.assertRaises(ValueError):
            node.AnimateDiffModel("sd.safetensors")

    def test_animatediff_uses_selected_seed_for_both_stages(self):
        from ssui.config import SSUIConfig
        from ssui.base import Prompt
        stub = self.stub()
        node = load_node("AnimateDiff", stub)
        config = SSUIConfig()("video")
        config["seed"] = 123
        model = types.SimpleNamespace(model_manager=object())
        node.AnimateDiffTextToVideo(config, model, Prompt("lake"), Prompt(""))
        image_pipe = stub.SDImagePipeline.from_model_manager.return_value
        video_pipe = stub.SDVideoPipeline.from_model_manager.return_value
        self.assertEqual(image_pipe.call_args.kwargs["seed"], 123)
        self.assertEqual(video_pipe.call_args.kwargs["seed"], 123)

    def test_auto_device_selection_and_cpu_precision(self):
        with patch.object(TorchDevice, "config", TorchDeviceConfig()), \
             patch("torch.cuda.is_available", return_value=False), \
             patch("torch.backends.mps.is_available", return_value=True):
            self.assertEqual(TorchDevice.choose_torch_device().type, "mps")
            self.assertEqual(TorchDevice.choose_torch_dtype(), torch.float16)
        with patch.object(TorchDevice, "config", TorchDeviceConfig()), \
             patch("torch.cuda.is_available", return_value=False), \
             patch("torch.backends.mps.is_available", return_value=False):
            self.assertEqual(TorchDevice.choose_torch_device().type, "cpu")
            self.assertEqual(TorchDevice.choose_torch_dtype(), torch.float32)

    def test_wan_runtime_preserves_cuda_bf16_and_uses_safe_mac_precision(self):
        runtime = load_node("_runtime", self.stub())
        for device, dtype in (("cpu", torch.float32), ("mps", torch.float32),
                              ("cuda:0", torch.bfloat16)):
            with self.subTest(device=device), patch.object(
                TorchDevice, "choose_torch_device", return_value=torch.device(device)
            ), patch.object(TorchDevice, "config", TorchDeviceConfig(precision="float32")):
                self.assertEqual(runtime.wan_runtime(), {"device": device, "torch_dtype": dtype})

    def test_wan_mps_precision_capability_and_override(self):
        runtime = load_node("_runtime", self.stub())
        with patch.object(TorchDevice, "choose_torch_device", return_value=torch.device("mps")), \
             patch("torch.backends.mps.is_available", return_value=True):
            for modern, precision, expected in ((False, "auto", torch.float32),
                                                (True, "auto", torch.bfloat16),
                                                (True, "float32", torch.float32)):
                with self.subTest(modern=modern, precision=precision), \
                     patch("torch.backends.mps.is_macos_or_newer", return_value=modern), \
                     patch.object(TorchDevice, "config", TorchDeviceConfig(precision=precision)):
                    self.assertEqual(runtime.wan_runtime()["torch_dtype"], expected)
            with patch.object(TorchDevice, "config", TorchDeviceConfig(precision="float16")):
                with self.assertRaisesRegex(ValueError, "overflow"):
                    runtime.wan_runtime()

    def test_hunyuan_import_does_not_initialize_cuda(self):
        with patch("torch.cuda.set_per_process_memory_fraction", side_effect=AssertionError("CUDA initialized")):
            load_node("Hunyuan", self.stub())
