"""Real CPU tensor lifecycle tests, independent of optional diffusion/CUDA packages."""
import os
import tempfile
import unittest
from unittest.mock import patch
import torch
from backend.runtime_offload import LoadPlan, configure_model, plan_load, weight_size
from backend.resource_monitor import GiB


class RuntimeOffloadTests(unittest.TestCase):
    def test_cpu_hooks_preserve_output_and_release_parameters(self):
        model = torch.nn.Sequential(torch.nn.Linear(4, 8), torch.nn.ReLU(), torch.nn.Linear(8, 2)).eval()
        x = torch.randn(3, 4)
        expected = model(x).detach()
        configure_model(model, LoadPlan('cpu_offload', 'cpu', 1000))
        self.assertTrue(all(p.device.type == 'meta' for p in model.parameters()))
        with torch.no_grad():
            for _ in range(3):
                self.assertTrue(torch.equal(expected, model(x)))
                self.assertTrue(all(p.device.type == 'meta' for p in model.parameters()))

    def test_disk_hooks_preserve_output_and_use_mapped_cpu_storage(self):
        model = torch.nn.Linear(3, 2).eval()
        x = torch.randn(2, 3)
        expected = model(x).detach()
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'SSUI_OFFLOAD_DIR': root}):
            configure_model(model, LoadPlan('disk_offload', 'cpu', 100))
            self.assertTrue(os.path.isfile(os.path.join(model._ssui_disk_backing.name, 'weights.pt')))
            with torch.no_grad():
                self.assertTrue(torch.equal(expected, model(x)))
                self.assertTrue(torch.equal(expected, model(x)))
            from accelerate.hooks import remove_hook_from_module
            remove_hook_from_module(model, recurse=True)
            model.load_state_dict({k: v.clone() for k, v in model.state_dict().items()}, assign=True)
            model._ssui_disk_backing.cleanup()

    def test_preflight_denial_happens_before_loader(self):
        resources = {'ram': {'total': 16*GiB, 'available': GiB}, 'gpus': []}
        with patch('backend.runtime_offload.snapshot', return_value=resources), \
             patch('backend.runtime_offload.confirm_disk_offload', side_effect=MemoryError('denied')) as confirm:
            with self.assertRaises(MemoryError):
                plan_load('video', estimated_bytes=8*GiB)
            confirm.assert_called_once_with('video', 8*GiB)

    def test_explicit_disk_still_requires_consent(self):
        resources = {'ram': {'total': 64*GiB, 'available': 60*GiB}, 'gpus': [{'index': 0, 'available': 24*GiB}]}
        with patch('backend.runtime_offload.snapshot', return_value=resources), \
             patch('backend.runtime_offload.confirm_disk_offload') as confirm:
            plan = plan_load('LTX', estimated_bytes=GiB, requested='disk')
            self.assertEqual(plan.mode, 'disk_offload')
            confirm.assert_called_once()

    def test_weight_files_counted_once(self):
        with tempfile.TemporaryDirectory() as root:
            from pathlib import Path
            weight = Path(root) / 'model.safetensors'
            weight.write_bytes(b'1234')
            (Path(root) / 'config.json').write_text('{}')
            self.assertEqual(weight_size([root, weight]), 4)

    def test_unknown_size_stops_before_model_load(self):
        with self.assertRaises(MemoryError):
            plan_load('unknown', '/not/a/local/weight')

    def test_diffsynth_actual_loader_keeps_execution_device_and_hooks_real_model(self):
        import ast
        from pathlib import Path
        from types import SimpleNamespace
        source = Path('extensions/Video/diffsynth/models/model_manager.py').read_text()
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ModelManager')
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('load_model', 'load_models')]
        namespace = {'os': os, 'torch': torch, 'load_state_dict': lambda p: torch.load(p, weights_only=True)}
        for method in methods:
            exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-diffsynth-loader>', 'exec'), namespace)
        loaded = torch.nn.Linear(3, 2).eval()
        detector = SimpleNamespace(match=lambda *args: True,
            load=lambda *args, **kwargs: (['tiny'], [loaded]))
        manager = SimpleNamespace(device='cpu', torch_dtype=torch.float32,
                                  model=[], model_path=[], model_name=[], model_detector=[detector])
        import types
        manager.load_model = types.MethodType(namespace['load_model'], manager)
        manager.load_models = types.MethodType(namespace['load_models'], manager)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'model.pt'
            torch.save(loaded.state_dict(), path)
            manager.load_models([str(path)])
        self.assertEqual(manager.device, 'cpu')
        from backend.runtime_offload import configure_pending
        configure_pending(manager.model[0], 'cpu')
        self.assertEqual(manager.model[0]._ssui_residency, 'cpu_offload')
        with torch.no_grad():
            self.assertEqual(manager.model[0](torch.ones(1, 3)).shape, (1, 2))

    def test_trellis_pipeline_device_is_execution_device_not_meta(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path('extensions/3D-Model/vendor/trellis/pipelines/base.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Pipeline')
        namespace = {'torch': torch, 'nn': torch.nn}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), '<actual-trellis-pipeline>', 'exec'), namespace)
        model = torch.nn.Linear(3, 2).eval()
        configure_model(model, LoadPlan('cpu_offload', 'cpu', 100))
        pipeline = namespace['Pipeline']({'tiny': model})
        pipeline.to('cpu')
        self.assertEqual(pipeline.device, torch.device('cpu'))
        self.assertTrue(all(p.device.type == 'meta' for p in model.parameters()))
        with self.assertRaises(RuntimeError):
            pipeline.to('cuda')

    def test_native_ltx_cli_receives_approved_effective_mode(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path('extensions/Video/ssui_video/LTX2.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_run_ltx')
        import subprocess
        namespace = {'_ltx_python': lambda: 'isolated-python', 'subprocess': subprocess, 'os': os, 'Path': Path, 'sys': __import__('sys'), '__file__': str(Path('extensions/Video/ssui_video/LTX2.py').resolve())}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<actual-ltx-runner>', 'exec'), namespace)
        with patch('backend.runtime_offload.plan_load', return_value=LoadPlan('disk_offload', 'cuda', GiB)) as planner, \
             patch('subprocess.Popen') as popen:
            popen.return_value.stdout = []
            popen.return_value.returncode = 0
            namespace['_run_ltx']('generate', ['--transformer-path', '/weights/model', '--offload', 'cpu'])
            command = popen.call_args.args[0]
            self.assertEqual(command[-2:], ['--offload', 'disk'])
            planner.assert_called_once_with('LTX-2.5', ['/weights/model'], requested='cpu')

    def test_failed_forward_releases_weights_for_retry(self):
        class Failing(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.weight = torch.nn.Parameter(torch.ones(2))
                self.fail = True
            def forward(self, x):
                if self.fail:
                    raise ValueError('intentional failure')
                return x * self.weight
        model = Failing()
        configure_model(model, LoadPlan('cpu_offload', 'cpu', 8))
        with self.assertRaisesRegex(ValueError, 'intentional'):
            model(torch.ones(2))
        self.assertEqual(model.weight.device.type, 'meta')
        model.fail = False
        with torch.no_grad():
            self.assertTrue(torch.equal(model(torch.ones(2)), torch.ones(2)))

    def test_lora_style_updates_restore_and_reinstall_residency(self):
        from backend.runtime_offload import materialize_for_update
        class Manager:
            def __init__(self, model):
                self.model = [model]
            @materialize_for_update
            def update(self):
                with torch.no_grad():
                    self.model[0].weight.add_(1)
        model = torch.nn.Linear(1, 1, bias=False)
        with torch.no_grad():
            model.weight.zero_()
        configure_model(model, LoadPlan('cpu_offload', 'cpu', 4))
        Manager(model).update()
        self.assertEqual(model.weight.device.type, 'meta')
        with torch.no_grad():
            self.assertTrue(torch.equal(model(torch.ones(1, 1)), torch.ones(1, 1)))

    def test_h3_disk_groups_have_separate_paths_and_no_stream_pinning(self):
        import ast
        from pathlib import Path
        from types import SimpleNamespace, ModuleType
        from unittest.mock import Mock
        import sys
        tree = ast.parse(Path('extensions/Video/ssui_video/h3_runner.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_enable_offload')
        namespace = {'Path': Path}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<actual-h3-groups>', 'exec'), namespace)
        hooks = ModuleType('diffusers.hooks')
        hooks.apply_group_offloading = Mock()
        pipe = SimpleNamespace(transformer=Mock(), text_encoder=Mock(), vae=Mock(), audio_vae=Mock())
        with patch.dict(sys.modules, {'diffusers.hooks': hooks}):
            namespace['_enable_offload'](pipe, disk_directory='/approved/offload')
        transformer_options = pipe.transformer.enable_group_offload.call_args.kwargs
        text_options = hooks.apply_group_offloading.call_args.kwargs
        self.assertEqual(transformer_options['offload_to_disk_path'], '/approved/offload/transformer')
        self.assertEqual(text_options['offload_to_disk_path'], '/approved/offload/text_encoder')
        self.assertFalse(transformer_options['use_stream'])

    def test_trellis_actual_checkpoint_loader_uses_empty_init_and_real_hooks(self):
        import ast
        import json
        from pathlib import Path
        from safetensors.torch import save_file
        tree = ast.parse(Path('extensions/3D-Model/vendor/trellis/models/__init__.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'from_pretrained')
        namespace = {'__getattr__': lambda name: torch.nn.Linear}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<actual-trellis-checkpoint>', 'exec'), namespace)
        original = torch.nn.Linear(3, 2).eval()
        x = torch.ones(1, 3)
        expected = original(x).detach()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'component'
            path.with_suffix('.json').write_text(json.dumps({'name': 'Linear', 'args': {'in_features': 3, 'out_features': 2}}))
            save_file(original.state_dict(), str(path.with_suffix('.safetensors')))
            with patch('backend.runtime_offload.plan_load', return_value=LoadPlan('cpu_offload', 'cpu', 32)) as planner:
                loaded = namespace['from_pretrained'](str(path))
            planner.assert_called_once()
            from backend.runtime_offload import configure_pending
            configure_pending(loaded, 'cpu')
            self.assertEqual(loaded.weight.device.type, 'meta')
            with torch.no_grad():
                self.assertTrue(torch.equal(expected, loaded(x)))

    def test_deferred_native_int8_disk_policy_keeps_quantized_output(self):
        from backend.runtime_offload import configure_pending
        from ssui.native_quantization import quantize_model_int8
        model = torch.nn.Sequential(torch.nn.Linear(3, 2)).eval()
        quantize_model_int8(model)
        x = torch.ones(1, 3)
        expected = model(x).detach()
        model._ssui_load_plan = LoadPlan('disk_offload', 'cpu', 100)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'SSUI_OFFLOAD_DIR': root}):
            self.assertTrue(configure_pending(model, 'cpu'))
            self.assertTrue(model._ssui_cpu_offload)
            with torch.no_grad():
                self.assertTrue(torch.equal(expected, model(x)))
                self.assertTrue(torch.equal(expected, model(x)))
            model.load_state_dict({k: v.clone() for k, v in model.state_dict().items()}, assign=True)
            model._ssui_disk_backing.cleanup()

    def test_fp8_preserves_native_casting_and_rejects_unsupported_disk(self):
        from backend.runtime_offload import configure_pending
        model = torch.nn.Linear(2, 2).to(dtype=torch.float8_e4m3fn)
        model._ssui_load_plan = LoadPlan('cpu_offload', 'cpu', 6)
        self.assertFalse(configure_pending(model, 'cpu'))
        self.assertEqual(model.weight.dtype, torch.float8_e4m3fn)
        self.assertFalse(hasattr(model, '_ssui_residency'))
        model._ssui_load_plan = LoadPlan('disk_offload', 'cpu', 6)
        with self.assertRaisesRegex(MemoryError, 'FP8'):
            configure_pending(model, 'cpu')
