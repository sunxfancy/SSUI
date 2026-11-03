"""LoRA numerical, routing and cache isolation regressions; no model downloads."""
import ast
import importlib.util
from pathlib import Path
import sys
import uuid
import types
import unittest
from unittest.mock import Mock, patch

import torch
from safetensors.torch import load_file, save_file
from backend.lora import apply_dit_lora, apply_diffusers_lora, apply_manager_lora, validate_lora
from tests import workflow_quantization_test as quant_tests
load_adapter = quant_tests.load_adapter

ROOT = Path(__file__).resolve().parents[1]


class LoraTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "build" / ("lora-test-" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        self.addCleanup(directory.rmdir)
        self.path = str(directory / "adapter.safetensors")
        self.addCleanup(lambda: Path(self.path).unlink(missing_ok=True))
        self.state = {"proj.lora_A.default.weight": torch.ones(1, 3),
                      "proj.lora_B.default.weight": torch.ones(2, 1)}
        save_file(self.state, self.path)
        spec = importlib.util.spec_from_file_location(
            "_ssui_numerical_lora", ROOT / "extensions/Video/diffsynth/lora/__init__.py")
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        utils = types.ModuleType("diffsynth.models.utils")
        utils.load_state_dict = load_file
        self.modules = {"diffsynth.models.utils": utils, "diffsynth.lora": loader}

    def test_real_checkpoint_changes_linear_output_with_negative_weight(self):
        model = torch.nn.Module()
        model.proj = torch.nn.Linear(3, 2, bias=False)
        model.proj.weight.data.zero_()
        with patch.dict(sys.modules, self.modules):
            apply_dit_lora(model, self.path, -0.5)
        torch.testing.assert_close(model.proj(torch.ones(1, 3)), torch.full((1, 2), -1.5))

    def test_fp8_storage_merge_uses_float_arithmetic(self):
        model = torch.nn.Module()
        model.proj = torch.nn.Linear(3, 2, bias=False).to(torch.float8_e4m3fn)
        model.proj.weight.data.zero_()
        with patch.dict(sys.modules, self.modules):
            apply_dit_lora(model, self.path, 0.5)
        self.assertEqual(model.proj.weight.dtype, torch.float8_e4m3fn)
        torch.testing.assert_close(model.proj.weight.float(), torch.full((2, 3), 0.5))

    def test_mismatched_shape_fails_before_mutation(self):
        model = torch.nn.Module()
        model.proj = torch.nn.Linear(4, 2, bias=False)
        before = model.proj.weight.detach().clone()
        with patch.dict(sys.modules, self.modules), self.assertRaisesRegex(ValueError, "shape"):
            apply_dit_lora(model, self.path)
        torch.testing.assert_close(model.proj.weight, before)

    def test_empty_and_unknown_adapters_rejected(self):
        model = torch.nn.Linear(3, 2)
        for state in ({"unrelated": torch.ones(1)}, self.state):
            save_file(state, self.path)
            with patch.dict(sys.modules, self.modules), self.assertRaises(ValueError):
                apply_dit_lora(model, self.path)

    def test_zero_skips_missing_file_and_nonfinite_is_rejected(self):
        self.assertFalse(validate_lora("missing.safetensors", 0))
        with self.assertRaises(FileNotFoundError):
            validate_lora("missing.safetensors", 1)
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                validate_lora("", value)

    def test_diffusers_adapter_weight_is_forwarded(self):
        pipe = Mock()
        apply_diffusers_lora(pipe, self.path, -0.25)
        pipe.set_adapters.assert_called_once_with(["ssui"], adapter_weights=[-0.25])
        pipe.load_lora_weights.assert_called_once_with(
            str(Path(self.path).parent), weight_name="adapter.safetensors", adapter_name="ssui")

    def test_legacy_loaders_apply_before_int8(self):
        fixtures = quant_tests.QuantizedAdapterTests()
        fixtures.setUp()
        for filename, names in (("Wan.py", ["WanVideoModel"]),
                                ("Wan2.py", ["Wan2T2VModel", "Wan2I2VModel"]),
                                ("Hunyuan.py", ["HunyuanVideoModel", "HunyuanImageToVideoModel"]),
                                ("CogVideo.py", ["CogVideoModel"])):
            module = load_adapter("extensions/Video/ssui_video/" + filename, fixtures.modules)
            for name in names:
                events = []
                with patch.object(module, "apply_manager_lora", side_effect=lambda *a: events.append(("lora", a))), \
                     patch.object(module, "quantize_manager_components", side_effect=lambda *a: events.append(("int8", a)), create=True), \
                     patch.object(module, "int8_quantizer", return_value=Mock(), create=True):
                    mode = "int8" if filename == "CogVideo.py" else "none"
                    getattr(module, name).load(quantization=mode, lora_path=self.path, lora_weight=0.6)
                self.assertEqual(events[0], ("lora", (fixtures.manager, self.path, 0.6)))
                if mode == "int8":
                    self.assertEqual(events[1][0], "int8")

    def test_wan22_experts_are_independent_and_apply_before_offload(self):
        fixtures = quant_tests.QuantizedAdapterTests()
        fixtures.setUp()
        pipe = Mock()
        utils = types.ModuleType("diffsynth.utils")
        utils.ModelConfig = lambda **kw: types.SimpleNamespace(**kw)
        wan = types.ModuleType("diffsynth.pipelines.wan_video_new")
        wan.WanVideoPipeline = Mock()
        wan.WanVideoPipeline.from_pretrained.return_value = pipe
        module = load_adapter("extensions/Video/ssui_video/Wan22.py", {
            **fixtures.modules, "diffsynth.utils": utils,
            "diffsynth.pipelines.wan_video_new": wan})
        for name in ("Wan22T2VA14BModel", "Wan22I2VA14BModel"):
            events = Mock()
            pipe.enable_vram_management = events.offload
            with patch.object(module, "apply_dit_lora", events.lora):
                getattr(module, name).load(high_noise_lora_path=self.path, high_noise_lora_weight=0.3,
                                          low_noise_lora_path=self.path, low_noise_lora_weight=-0.7)
            self.assertEqual(events.mock_calls[0].args, (pipe.dit, self.path, 0.3))
            self.assertEqual(events.mock_calls[1].args, (pipe.dit2, self.path, -0.7))
            self.assertEqual(events.mock_calls[2][0], "offload")

    def test_flux2_lora_does_not_mutate_cached_base(self):
        from tests.flux2_test import _FakePipeline
        from ssui_image import Flux2
        Flux2.Flux2KleinModel.clear_cache()
        self.addCleanup(Flux2.Flux2KleinModel.clear_cache)
        fake = types.SimpleNamespace(Flux2KleinPipeline=_FakePipeline)
        with patch.dict(sys.modules, {"diffusers": fake}), \
             patch.object(Flux2, "_resolve_device", return_value="cpu"), \
             patch.object(_FakePipeline, "load_lora_weights", create=True), \
             patch.object(_FakePipeline, "set_adapters", create=True):
            base = Flux2.Flux2KleinModel.load("fake/base")
            adapted = Flux2.Flux2KleinModel.load("fake/base", lora_path=self.path)
            again = Flux2.Flux2KleinModel.load("fake/base")
        self.assertIs(base.pipeline, again.pipeline)
        self.assertIsNot(base.pipeline, adapted.pipeline)

    def test_legacy_manager_uses_real_loader_and_rejects_empty_adapter(self):
        source = ROOT / "extensions/Video/diffsynth/models/lora.py"
        dependencies = dict(self.modules)
        # Stub only heavyweight model classes; execute the actual vendor loader.
        for node in ast.parse(source.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                name = "diffsynth.models." + node.module
                module = types.ModuleType(name)
                for alias in node.names:
                    setattr(module, alias.name, type(alias.name, (torch.nn.Module,), {}))
                dependencies[name] = module
        spec = importlib.util.spec_from_file_location("diffsynth.models.lora", source)
        legacy = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, dependencies):
            spec.loader.exec_module(legacy)
        dependencies["diffsynth.models.lora"] = legacy
        model = torch.nn.Module()
        model.proj = torch.nn.Linear(3, 2, bias=False)
        model.proj.weight.data.zero_()
        manager = types.SimpleNamespace(model=[model])
        with patch.dict(sys.modules, dependencies):
            apply_manager_lora(manager, self.path, 0.5)
            torch.testing.assert_close(model.proj.weight, torch.full((2, 3), 0.5))
            save_file({"unrelated": torch.ones(1)}, self.path)
            with self.assertRaisesRegex(ValueError, "no compatible"):
                apply_manager_lora(manager, self.path)
        # Civitai conversion must also work on CPU-only installations.
        converted = legacy.LoRAFromCivitai().convert_state_dict({
            "lora_unet_proj.lora_up.weight": torch.ones(2, 1),
            "lora_unet_proj.lora_down.weight": torch.ones(1, 3)}, alpha=0.25)
        torch.testing.assert_close(converted["proj.weight"], torch.full((2, 3), 0.25))

    def test_manager_lora_precedes_new_memory_policy(self):
        fixtures = quant_tests.QuantizedAdapterTests()
        fixtures.setUp()
        for filename, names in (("Wan.py", ["WanVideoModel"]),
                                ("Wan2.py", ["Wan2T2VModel", "Wan2I2VModel"]),
                                ("Hunyuan.py", ["HunyuanVideoModel", "HunyuanImageToVideoModel"]),
                                ("CogVideo.py", ["CogVideoModel"])):
            module = load_adapter("extensions/Video/ssui_video/" + filename, fixtures.modules)
            for name in names:
                events = Mock()
                with patch.object(module, "apply_manager_lora", events.lora), \
                     patch.object(module, "configure_diffsynth_manager", events.memory), \
                     patch.object(module, "int8_quantizer", return_value=Mock(), create=True), \
                     patch.object(module, "quantize_manager_components", events.quantize, create=True):
                    getattr(module, name).load(quantization="int8", cpu_offload=True,
                                              lora_path=self.path, lora_weight=0.6)
                self.assertEqual(events.mock_calls[0][0], "lora")
                self.assertEqual(events.mock_calls[-1][0], "memory")
                options = events.memory.call_args.args[1]
                self.assertEqual(options.quantization, "int8")
                self.assertTrue(options.cpu_offload)
