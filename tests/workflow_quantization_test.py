"""Quantization contracts without downloading model weights or requiring CUDA."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from backend.quantization.workflow import (
    fp8_storage_dtype,
    int8_quantizer,
    load_dit_with_storage_dtype,
)

ROOT = Path(__file__).resolve().parents[1]
HAS_TORCH = importlib.util.find_spec("torch") is not None


def load_adapter(filename, modules):
    name = "ssui_video._quantization_adapter" if "/ssui_video/" in filename else "quantization_adapter_under_test"
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


def vendor_namespaces():
    # Load only the numerical modules under an isolated namespace, bypassing
    # DiffSynth's package initializer and its unrelated model dependencies.
    root = ROOT / "extensions/Video/diffsynth"
    modules = {}
    for suffix, path in (("", root), (".models", root / "models"),
                         (".vram_management", root / "vram_management")):
        name = "_ssui_quant_diffsynth" + suffix
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        modules[name] = module
    return modules


class QuantizationOptionTests(unittest.TestCase):
    def test_none_does_not_import_optional_dependencies(self):
        model = object()
        with patch.dict(sys.modules, {"torchao": None, "torch": None}):
            self.assertIs(int8_quantizer("none")(model), model)
            self.assertEqual(fp8_storage_dtype("none", "bf16"), "bf16")

    def test_unsupported_modes_fail_explicitly(self):
        for mode in ("int4", "INT8", None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                int8_quantizer(mode)
        with self.assertRaises(ValueError):
            fp8_storage_dtype("int8", "bf16")

    def test_missing_torchao_has_actionable_error(self):
        with patch.dict(sys.modules, {"torchao": None, "torchao.quantization": None}):
            with self.assertRaisesRegex(RuntimeError, "optional torchao.*compatible"):
                int8_quantizer("int8")

    def test_legacy_torchao_recipe_is_supported(self):
        ao = types.ModuleType("torchao.quantization")
        ao.int8_weight_only = Mock(return_value="legacy-int8-recipe")
        ao.quantize_ = Mock()
        with patch.dict(sys.modules, {"torchao.quantization": ao}):
            self.assertTrue(callable(int8_quantizer("int8")))
        ao.int8_weight_only.assert_called_once_with()

    def test_none_preserves_legacy_loader_call(self):
        manager = Mock()
        paths = ["dit", "text_encoder", "vae"]
        load_dit_with_storage_dtype(
            manager, paths, quantization="none", torch_dtype="bf16", device="cpu"
        )
        manager.load_models.assert_called_once_with(paths, torch_dtype="bf16", device="cpu")

    def test_prepare_exposes_options_without_torchao(self):
        from ssui.config import SSUIConfig
        from ssui.quantization import FP8Quantization, Int8Quantization

        config = SSUIConfig()
        config.set_prepared()
        with patch.dict(sys.modules, {"torchao": None, "torch": None}):
            self.assertEqual(FP8Quantization(config("Wan Model")), "none")
            self.assertEqual(Int8Quantization(config("Trellis Model")), "none")
        self.assertEqual(config._config["Wan Model"]["quantization"]["args"].options, ("none", "fp8"))
        self.assertEqual(config._config["Trellis Model"]["quantization"]["args"].options, ("none", "int8"))
        config.set_prepared(False)
        config("Wan Model")["quantization"] = "fp8"
        self.assertEqual(FP8Quantization(config("Wan Model")), "fp8")

    def test_example_workflows_prepare_without_loading_and_forward_selection(self):
        import inspect

        cases = {
            "Wan": ("WanVideoModel", "WanImageTextToVideo"),
            "Wan2": ("Wan2T2VModel", "Wan2I2VModel", "Wan2TextToVideo", "Wan2ImageToVideo"),
            "Wan22": ("Wan22TI2VModel", "Wan22T2VA14BModel", "Wan22I2VA14BModel",
                      "Wan22TextToVideo", "Wan22ImageToVideo", "Wan22T2VA14BTextToVideo",
                      "Wan22I2VA14BImageToVideo"),
            "Hunyuan": ("HunyuanVideoModel", "HunyuanImageToVideoModel",
                        "HunyuanTextToVideo", "HunyuanImageToVideo"),
            "CogVideo": ("CogVideoModel", "CogVideoTextToVideo"),
            "LTX2": ("LTX2TextToVideo", "LTX2ImageToVideo"),
            "MiniMaxH3": ("H3TextToVideo", "H3ImageToVideo"),
        }
        modules = {}
        for filename, names in cases.items():
            key = f"ssui_video.{filename}"
            modules[key] = types.ModuleType(key)
            for name in names:
                setattr(modules[key], name, Mock())
        trellis = types.ModuleType("ssui_3dmodel.Trellis")
        trellis.TrellisModel = Mock()
        trellis.GenModel = Mock()
        modules["ssui_3dmodel.Trellis"] = trellis
        for filename, names in {
            "Pixal3D": ("Pixal3DModel", "GenPixal3DModel"),
            "WorldClaw": ("WorldClawModel", "GenWorldClawScene"),
        }.items():
            key = f"ssui_3dmodel.{filename}"
            modules[key] = types.ModuleType(key)
            for name in names:
                setattr(modules[key], name, Mock())
        flux = types.ModuleType("ssui_image.Flux")
        for name in ("FluxModel", "FluxClip", "FluxLatent", "FluxDenoise", "FluxLatentDecode"):
            setattr(flux, name, Mock())
        modules["ssui_image.Flux"] = flux
        targets = {
            "workflow-3d.py": {"img2mesh_quantized": "TrellisModel"},
            "workflow-video.py": {"img2vid": "WanVideoModel", "txt2vid": "HunyuanVideoModel"},
            "workflow-video-local.py": {
                "txt2vid_wan2": "Wan2T2VModel", "img2vid_wan2": "Wan2I2VModel",
                "img2vid_hunyuan": "HunyuanImageToVideoModel", "txt2vid_cogvideo": "CogVideoModel",
                "txt2vid_wan22": "Wan22TI2VModel", "img2vid_wan22": "Wan22TI2VModel",
                "txt2vid_wan22_a14b": "Wan22T2VA14BModel", "img2vid_wan22_a14b": "Wan22I2VA14BModel",
            },
        }
        for filename, functions in targets.items():
            # Avoid registering test-only workflow functions globally.
            with patch("ssui.annotation.callables", []):
                module = load_adapter(f"examples/advance/{filename}", modules)
            if filename == "workflow-3d.py":
                self.assertEqual(list(inspect.signature(module.img2mesh).parameters), ["model", "image"])
            for function_name, model_name in functions.items():
                with self.subTest(workflow=function_name):
                    cls = getattr(module, model_name)
                    cls.reset_mock()
                    function = getattr(module, function_name)
                    args = {key: None for key in inspect.signature(function).parameters}
                    module.config.set_prepared()
                    function(**args)
                    cls.load.assert_not_called()
                    options_name = f"{model_name} Options"
                    setting = module.config._config[options_name]["quantization"]
                    self.assertEqual(setting["default"], "none")
                    mode = "int8" if model_name in ("TrellisModel", "CogVideoModel") else "fp8"
                    self.assertIn(mode, setting["args"].options)
                    module.config.set_prepared(False)
                    module.config(options_name)["quantization"] = mode
                    function(**args)
                    self.assertEqual(cls.load.call_args.kwargs["quantization"], mode)


@unittest.skipUnless(HAS_TORCH, "PyTorch is required for adapter contracts")
class QuantizedAdapterTests(unittest.TestCase):
    def setUp(self):
        import torch
        self.torch = torch
        self.manager = Mock()
        self.diffsynth = types.ModuleType("diffsynth")
        self.diffsynth.ModelManager = Mock(return_value=self.manager)
        self.diffsynth.download_models = Mock()
        self.diffsynth.download_customized_models = Mock()
        for name in ("WanVideoPipeline", "HunyuanVideoPipeline", "CogVideoPipeline",
                     "SDImagePipeline", "SDVideoPipeline", "FlowMatchScheduler", "save_video"):
            setattr(self.diffsynth, name, Mock())
        self.modelscope = types.ModuleType("modelscope")
        self.modelscope.snapshot_download = Mock()
        runtime = types.ModuleType("ssui_video._runtime")
        runtime.wan_runtime = lambda: {"device": "cuda", "torch_dtype": torch.bfloat16}
        devices = types.ModuleType("backend.util.devices")
        devices.TorchDevice = Mock()
        devices.TorchDevice.choose_torch_device.return_value = torch.device("cuda")
        devices.TorchDevice.choose_torch_dtype.return_value = torch.bfloat16
        self.modules = {"diffsynth": self.diffsynth, "modelscope": self.modelscope,
                        "ssui_video._runtime": runtime, "backend.util.devices": devices}

    def test_legacy_wan_only_casts_dit_and_rejects_bad_modes_before_download(self):
        for filename, classes in (
            ("Wan.py", ("WanVideoModel",)),
            ("Wan2.py", ("Wan2T2VModel", "Wan2I2VModel")),
        ):
            module = load_adapter(f"extensions/Video/ssui_video/{filename}", self.modules)
            for name in classes:
                with self.subTest(name=name):
                    self.manager.reset_mock()
                    getattr(module, name).load(quantization="fp8")
                    calls = self.manager.load_models.call_args_list
                    self.assertEqual(len(calls), 2)
                    self.assertEqual(len(calls[0].args[0]), 1)
                    self.assertEqual(calls[0].kwargs["torch_dtype"], self.torch.float8_e4m3fn)
                    self.assertEqual(calls[1].kwargs["torch_dtype"], self.torch.bfloat16)
                    self.assertTrue(all(call.kwargs["device"] == "cpu" for call in calls))
                    self.modelscope.snapshot_download.reset_mock()
                    with self.assertRaises(ValueError):
                        getattr(module, name).load(quantization="int4")
                    self.modelscope.snapshot_download.assert_not_called()

    def test_fp8_rejects_mps_without_changing_none_mode(self):
        torch = self.torch
        self.assertEqual(fp8_storage_dtype("none", torch.float32, device="mps"), torch.float32)
        with self.assertRaisesRegex(RuntimeError, "not supported on MPS"):
            fp8_storage_dtype("fp8", torch.float32, device="mps")
        self.modules["ssui_video._runtime"].wan_runtime = lambda: {
            "device": "mps", "torch_dtype": torch.float32,
        }
        module = load_adapter("extensions/Video/ssui_video/Wan2.py", self.modules)
        with self.assertRaisesRegex(RuntimeError, "not supported on MPS"):
            module.Wan2T2VModel.load(quantization="fp8")
        self.modelscope.snapshot_download.assert_not_called()

    def test_hunyuan_only_casts_dit(self):
        module = load_adapter("extensions/Video/ssui_video/Hunyuan.py", self.modules)
        for name in ("HunyuanVideoModel", "HunyuanImageToVideoModel"):
            with self.subTest(name=name):
                self.manager.reset_mock()
                getattr(module, name).load(quantization="fp8")
                calls = self.manager.load_models.call_args_list
                self.assertEqual(calls[0].kwargs["torch_dtype"], self.torch.float8_e4m3fn)
                self.assertEqual(calls[1].kwargs["torch_dtype"], self.torch.float16)

    def test_fp8_storage_executes_with_bf16_diffsynth_linear(self):
        from importlib import import_module
        torch = self.torch
        with patch.dict(sys.modules, vendor_namespaces()):
            layers = import_module("_ssui_quant_diffsynth.vram_management.layers")
        torch.manual_seed(42)
        linear = torch.nn.Linear(128, 128).to(dtype=torch.bfloat16).eval()
        x = torch.randn(2, 128, dtype=torch.bfloat16)
        with torch.inference_mode():
            expected = linear(x)
            linear.to(dtype=fp8_storage_dtype("fp8", torch.bfloat16))
            wrapped = layers.AutoWrappedLinear(
                linear, offload_dtype=torch.float8_e4m3fn, offload_device="cpu",
                onload_dtype=torch.float8_e4m3fn, onload_device="cpu",
                computation_dtype=torch.bfloat16, computation_device="cpu", vram_limit=None,
            )
            actual = wrapped(x)
        self.assertEqual(wrapped.weight.dtype, torch.float8_e4m3fn)
        self.assertEqual(actual.dtype, torch.bfloat16)
        self.assertFalse(wrapped.enable_fp8)  # no FP8 activation kernel
        torch.testing.assert_close(actual, expected, atol=0.07, rtol=0.1)

    def test_wan22_keeps_compute_and_non_dit_components_bf16(self):
        utils = types.ModuleType("diffsynth.utils")
        utils.ModelConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
        wan = types.ModuleType("diffsynth.pipelines.wan_video_new")
        wan.WanVideoPipeline = Mock()
        modules = {**self.modules, "diffsynth.utils": utils,
                   "diffsynth.pipelines.wan_video_new": wan}
        module = load_adapter("extensions/Video/ssui_video/Wan22.py", modules)
        for name, expert_count in (("Wan22TI2VModel", 1), ("Wan22T2VA14BModel", 2),
                                   ("Wan22I2VA14BModel", 2)):
            with self.subTest(name=name):
                getattr(module, name).load(quantization="fp8")
                kwargs = wan.WanVideoPipeline.from_pretrained.call_args.kwargs
                self.assertEqual(kwargs["torch_dtype"], self.torch.bfloat16)
                configs = kwargs["model_configs"]
                dit = [c for c in configs if "diffusion_pytorch" in c.origin_file_pattern]
                self.assertEqual(len(dit), expert_count)
                self.assertTrue(all(c.offload_dtype == self.torch.float8_e4m3fn for c in dit))
                self.assertTrue(all(not hasattr(c, "offload_dtype") for c in configs if c not in dit))

    def test_int8_video_loads_on_cpu_quantizes_selected_components_then_moves(self):
        for filename, name, constructor, components in (
            ("CogVideo.py", "CogVideoModel", False, ("cog_dit", "flux_text_encoder_2")),
            ("AnimateDiff.py", "AnimateDiffModel", True, ("sd_unet", "sd_text_encoder")),
        ):
            module = load_adapter(f"extensions/Video/ssui_video/{filename}", self.modules)
            quantize = Mock()
            self.manager.reset_mock()
            with patch.object(module, "int8_quantizer", return_value=quantize):
                cls = getattr(module, name)
                cls(quantization="int8") if constructor else cls.load(quantization="int8")
            self.assertEqual([c.args[0] for c in self.manager.fetch_model.call_args_list], list(components))
            self.assertEqual(quantize.call_count, len(components))
            self.manager.to.assert_called_once_with("cuda")
            self.assertEqual(self.manager.device, "cuda")
            self.assertEqual(self.diffsynth.ModelManager.call_args.kwargs["device"], "cpu")

    def test_trellis_quantizes_flows_and_conditioner_before_cuda(self):
        pipeline = Mock()
        pipeline.models = {name: object() for name in (
            "sparse_structure_flow_model", "slat_flow_model", "image_cond_model",
            "slat_decoder_mesh", "slat_decoder_gs",
        )}
        trellis = types.ModuleType("trellis.pipelines.trellis_image_to_3d")
        trellis.TrellisImageTo3DPipeline = Mock()
        trellis.TrellisImageTo3DPipeline.from_pretrained.return_value = pipeline
        utils = types.ModuleType("trellis.utils")
        utils.postprocessing_utils = Mock()
        module = load_adapter("extensions/3D-Model/ssui_3dmodel/Trellis.py", {
            "trellis.pipelines.trellis_image_to_3d": trellis, "trellis.utils": utils,
        })
        quantize = Mock(side_effect=lambda model: pipeline.cuda.assert_not_called())
        with patch.object(module, "int8_quantizer", return_value=quantize), \
                patch.dict(sys.modules, {**self.modules, "trellis.pipelines.trellis_image_to_3d": trellis}), \
                patch("torch.cuda.is_available", return_value=True):
            result = module.TrellisModel.load("local-model", quantization="int8")
        self.assertIs(result.model, pipeline)
        self.assertEqual([c.args[0] for c in quantize.call_args_list], list(pipeline.models.values())[:3])
        pipeline.cuda.assert_called_once()


@unittest.skipUnless(HAS_TORCH and importlib.util.find_spec("torchao") is not None,
                     "Optional torchao required for numerical INT8 regression")
class Int8NumericalTests(unittest.TestCase):
    def test_weight_storage_shrinks_and_custom_linear_forward_survives(self):
        import torch

        class SparseInput:
            def __init__(self, feats):
                self.feats = feats

            def replace(self, feats):
                return SparseInput(feats)

        # Exercise the real vendored SparseLinear without importing CUDA-only
        # sparse convolution/rendering dependencies.
        package = types.ModuleType("_ssui_quant_sparse")
        package.SparseTensor = SparseInput
        path = ROOT / "extensions/3D-Model/vendor/trellis/modules/sparse/linear.py"
        spec = importlib.util.spec_from_file_location("_ssui_quant_sparse.linear", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"_ssui_quant_sparse": package}):
            spec.loader.exec_module(module)
        for dtype in (torch.float32, torch.float16, torch.bfloat16):
            with self.subTest(dtype=dtype):
                torch.manual_seed(42)
                model = torch.nn.Sequential(module.SparseLinear(128, 128)).to(dtype=dtype).eval()
                x = SparseInput(torch.randn(2, 128, dtype=dtype))
                with torch.inference_mode():
                    expected = model(x).feats
                    int8_quantizer("int8")(model)
                    actual = model(x).feats
                self.assertIsInstance(model[0], module.SparseLinear)
                weight = model[0].weight
                layout = weight.tensor_impl if hasattr(weight, "tensor_impl") else weight.layout_tensor
                tensors = layout.get_plain()
                packed = tensors[0]
                self.assertEqual(packed.dtype, torch.int8)
                self.assertEqual(weight.dtype, dtype)
                storage_bytes = sum(t.numel() * t.element_size() for t in tensors if torch.is_tensor(t))
                self.assertLess(storage_bytes,
                                128 * 128 * torch.tensor([], dtype=dtype).element_size())
                torch.testing.assert_close(actual, expected, atol=0.03, rtol=0.08)


if __name__ == "__main__":
    unittest.main()
