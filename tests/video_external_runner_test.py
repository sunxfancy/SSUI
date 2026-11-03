"""External video runners must retain accelerator selection without model downloads."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1] / "extensions/Video/ssui_video"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalVideoRunnerTest(unittest.TestCase):
    def test_h3_swap_guard_stops_before_computation(self):
        import torch
        block = torch.nn.Identity()
        pipe = types.SimpleNamespace(
            text_encoder=types.SimpleNamespace(model=types.SimpleNamespace(language_model=types.SimpleNamespace(layers=[block]))),
            transformer=types.SimpleNamespace(transformer_blocks=[]),
            vae=types.SimpleNamespace(decoder=types.SimpleNamespace(transformer_blocks=[])))
        with patch("psutil.swap_memory", side_effect=[types.SimpleNamespace(used=0), types.SimpleNamespace(used=3*1024**3)]), \
             patch("psutil.virtual_memory", return_value=types.SimpleNamespace(available=4*1024**3)), \
             patch.object(torch.mps, "synchronize") as sync:
            load("h3_runner")._guard_mps_memory(pipe)
            with self.assertRaisesRegex(RuntimeError, "swap grew"):
                block(torch.zeros(1))
            sync.assert_not_called()

    def test_h3_parent_guard_terminates_unresponsive_worker(self):
        import subprocess
        spec = importlib.util.spec_from_file_location("h3_smoke", ROOT.parents[2] / "scripts/h3_mac_smoke.py")
        smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smoke)
        process = MagicMock()
        process.wait.side_effect = [subprocess.TimeoutExpired(["worker"], 1), 0]
        process.__enter__.return_value = process
        with patch.object(smoke.subprocess, "Popen", return_value=process), \
             patch("psutil.swap_memory", side_effect=[types.SimpleNamespace(used=0), types.SimpleNamespace(used=3*1024**3)]), \
             patch("psutil.virtual_memory", return_value=types.SimpleNamespace(available=4*1024**3)):
            with self.assertRaisesRegex(RuntimeError, "swap growth=3.00"):
                smoke._run_guarded(["worker"])
        process.terminate.assert_called_once()

    def test_h3_smoke_rejects_too_short_video_before_loading(self):
        import contextlib
        import io
        spec = importlib.util.spec_from_file_location("h3_smoke", ROOT.parents[2] / "scripts/h3_mac_smoke.py")
        smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smoke)
        with patch.object(sys, "argv", ["smoke", "--frames", "22"]), \
             patch.object(smoke, "_run_guarded") as run, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                smoke.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_h3_mps_offload_preserves_host_weights(self):
        hooks = types.ModuleType("diffusers.hooks")
        hooks.apply_group_offloading = MagicMock()
        pipe = MagicMock()
        runner = load("h3_runner")
        with patch.dict(sys.modules, {"diffusers.hooks": hooks}), patch.object(runner, "_checkpoint_offload") as stream:
            runner._enable_offload(pipe, device="mps", model_root=ROOT)
        hooks.apply_group_offloading.assert_not_called()
        self.assertEqual(stream.call_count, 3)
        for call, name in zip(stream.call_args_list, ("transformer", "text_encoder", "vae")):
            self.assertIs(call.args[0], getattr(pipe, name))
            self.assertEqual(call.args[1], ROOT / name)
        pipe.vae.to.assert_not_called()
        pipe.audio_vae.to.assert_called_once_with("mps")

    def test_ltx_refuses_cpu_and_mps_quantization(self):
        import torch
        helpers = types.ModuleType("ltx_pipelines.utils.helpers")
        for device, extra, message in (("cpu", [], "fallback"),
                                       ("mps", ["--quantization", "fp8-cast"], "BF16")):
            helpers.get_device = lambda: torch.device(device)
            with patch.dict(sys.modules, {"ltx_pipelines.utils.helpers": helpers}), \
                 patch.object(sys, "argv", ["runner", "--module", "distilled", *extra]), \
                 self.assertRaisesRegex((RuntimeError, ValueError), message):
                load("ltx_runner").main()

    def test_ltx_disk_slots_are_bounded_and_restored(self):
        import torch
        builder = types.ModuleType("ltx_core.block_streaming.builder")
        class Builder:
            blocks_prefix = "transformer_blocks"
            def _load_non_block_weights(self, *args):
                return None
            def build(self, **kwargs):
                return kwargs
        original = Builder.build
        builder.StreamingModelBuilder = Builder
        builder._PREFETCH_DEPTH = 2
        package = types.ModuleType("ltx_core.block_streaming")
        package.builder = builder
        prompt = types.ModuleType("ltx_pipelines.utils.blocks.prompt_encoder")
        prompt.PromptEncoder = type("PromptEncoder", (), {"_build_embeddings_processor": lambda self: None})
        with patch.dict(sys.modules, {"ltx_core.block_streaming": package,
                                      "ltx_pipelines.utils.blocks.prompt_encoder": prompt}):
            with load("ltx_runner")._bounded_disk_streaming():
                settings = Builder().build(device=torch.device("mps"), dtype=torch.bfloat16)
                self.assertEqual(settings["cpu_slots_count"], 1)
                self.assertEqual(settings["gpu_slots_count"], 1)
                self.assertEqual(builder._PREFETCH_DEPTH, 0)
                cuda = Builder().build(device=torch.device("cuda"), cpu_slots_count=3)
                self.assertEqual(cuda["cpu_slots_count"], 3)
            self.assertIs(Builder.build, original)
            self.assertEqual(builder._PREFETCH_DEPTH, 2)

    def test_ltx_filters_only_weights_absent_from_model(self):
        import torch
        model = torch.nn.Linear(2, 3)
        model.register_buffer("scale", torch.ones(1))
        keys = [("prefix.weight", "weight"), ("prefix.bias", "bias"),
                ("prefix.scale", "scale"), ("prefix.unused_connector", "unused_connector")]
        self.assertEqual(load("ltx_runner")._needed_non_block_keys(model, keys), keys[:3])

    def test_ltx_text_teardown_releases_buffer_provider(self):
        import weakref
        class Provider:
            def cleanup(self):
                self.cleaned = True
        class Wrapper:
            def teardown(self):
                self._provider.cleanup()
        wrapper = Wrapper()
        provider = Provider()
        wrapper._provider = provider
        reference = weakref.ref(provider)
        load("ltx_runner")._teardown_text_streaming(wrapper)
        self.assertTrue(provider.cleaned)
        self.assertIsNone(wrapper._provider)
        del provider
        self.assertIsNone(reference())

    def test_ltx_forwards_supported_arguments(self):
        import torch
        helpers = types.ModuleType("ltx_pipelines.utils.helpers")
        helpers.get_device = lambda: torch.device("mps")
        runner = load("ltx_runner")
        with patch.object(runner, "_bounded_disk_streaming"), \
             patch.dict(sys.modules, {"ltx_pipelines.utils.helpers": helpers}), \
             patch.object(sys, "argv", ["runner", "--module", "distilled", "--offload", "disk"]), \
             patch.object(torch.mps, "set_per_process_memory_fraction"), \
             patch("runpy.run_module") as run:
            runner.main()
            self.assertEqual(sys.argv[1:], ["--offload", "disk"])
        run.assert_called_once_with("ltx_pipelines.distilled", run_name="__main__")
