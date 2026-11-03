"""Real CPU INT8 checks and component residency lifecycle regression tests."""
import importlib.util
import unittest
from unittest.mock import patch

import torch

from backend.util.calc_tensor_size import calc_tensor_size
from ssui.config import SSUIConfig
from ssui.model_memory import ModelMemoryOptions, model_memory, offload_component


class Component(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = torch.nn.Linear(64, 64)
        self.moves = []
        self.resident = False

    def to(self, device, *args, **kwargs):
        # Simulate placement, while all numerical execution stays on real CPU.
        self.moves.append(str(device))
        self.resident = str(device) == 'cuda'
        return super().to('cpu')

    def forward(self, x):
        if not self.resident:
            raise AssertionError('component called while offloaded')
        return self.linear(x)

    def generate(self, x):
        result = self(x)
        if not self.resident:
            raise AssertionError('nested forward prematurely offloaded its caller')
        return result

    @torch.inference_mode()
    def inference(self, x):
        yield self(x)
        if not self.resident:
            raise AssertionError('stream prematurely offloaded')
        yield self(x)

    def decode(self, x):
        raise ValueError('decode failed')


class ModelMemoryTest(unittest.TestCase):
    def test_invalid_policy(self):
        with self.assertRaises(ValueError):
            ModelMemoryOptions('invalid')
        with self.assertRaises(TypeError):
            ModelMemoryOptions(cpu_offload='false')

    def test_disabled_quantization_preserves_parameters(self):
        model = torch.nn.Linear(64, 64)
        weight = model.weight
        ModelMemoryOptions().quantize(model)
        self.assertIs(model.weight, weight)
        self.assertFalse(hasattr(model, '_ssui_int8'))

    def test_real_int8_reduces_storage_and_preserves_inference(self):
        torch.manual_seed(17)
        model = torch.nn.Sequential(torch.nn.Linear(256, 256), torch.nn.ReLU(), torch.nn.Linear(256, 64)).eval()
        x = torch.randn(4, 256)
        expected = model(x)
        before = sum(calc_tensor_size(t) for t in model.state_dict().values())
        options = ModelMemoryOptions('int8')
        options.quantize(model)
        after = sum(calc_tensor_size(t) for t in model.state_dict().values())
        self.assertLess(after, before * 0.4)
        torch.testing.assert_close(model(x), expected, atol=0.02, rtol=0.04)
        first_weight = model[0]._int8_weight
        options.quantize(model)
        self.assertIs(model[0]._int8_weight, first_weight)
        # State dict roundtrip is used by the image cache's RAM copy.
        model.load_state_dict(model.state_dict(), assign=True)
        torch.testing.assert_close(model(x), expected, atol=0.02, rtol=0.04)

    def test_quantization_with_offload_and_duplicate_components(self):
        model = Component()
        ModelMemoryOptions('int8', True).configure([model, model])
        self.assertTrue(model._ssui_int8)
        model.generate(torch.randn(1, 64))
        self.assertEqual(model.moves, ['cpu', 'cuda', 'cpu'])
        self.assertFalse(model.resident)

    def test_nested_call_releases_once(self):
        model = Component()
        offload_component(model)
        model.generate(torch.randn(1, 64))
        self.assertEqual(model.moves, ['cpu', 'cuda', 'cpu'])

    def test_exception_releases_component(self):
        model = Component()
        offload_component(model)
        with self.assertRaisesRegex(ValueError, 'decode failed'):
            model.decode(None)
        self.assertFalse(model.resident)
        model.generate(torch.randn(1, 64))
        self.assertFalse(model.resident)

    def test_decorated_stream_releases_on_close_and_exhaustion(self):
        model = Component()
        offload_component(model)
        stream = model.inference(torch.randn(1, 64))
        self.assertFalse(model.resident)
        next(stream)
        self.assertTrue(model.resident)
        stream.close()
        self.assertFalse(model.resident)
        self.assertEqual(len(list(model.inference(torch.randn(1, 64)))), 2)
        self.assertFalse(model.resident)

    def test_quantization_never_imports_torchao(self):
        import builtins
        original_import = builtins.__import__
        def importing(name, *args, **kwargs):
            if name.startswith('torchao'):
                raise AssertionError('External quantizer was imported')
            return original_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=importing):
            model = torch.nn.Linear(64, 64)
            ModelMemoryOptions('int8').quantize(model)
            self.assertEqual(model._int8_weight.dtype, torch.int8)

    def test_controls_register_without_loading_during_prepare(self):
        config = SSUIConfig()
        config.set_prepared(True)
        model_memory(config('Memory'), cpu_offload_default=True)
        self.assertEqual(config._config['Memory']['quantization']['args'].options, ('none', 'int8'))
        config.set_prepared(False)
        config['quantization'] = 'int8'
        config['cpu_offload'] = False
        self.assertEqual(model_memory(config('Memory')), {'quantization': 'int8', 'cpu_offload': False})


class VideoLoaderMemoryTest(unittest.TestCase):
    def test_model_manager_loaders_apply_both_options(self):
        """Exercise actual public loaders without downloads or a GPU."""
        import sys
        import types
        from pathlib import Path

        class Manager:
            def __init__(self, **kwargs):
                self.model = []
                self.device = kwargs.get('device', 'cuda')
                self.torch_dtype = kwargs.get('torch_dtype', torch.float16)
                self.load_devices = []

            def to(self, device):
                for component in self.model:
                    component.to(device)
            def fetch_model(self, name):
                return self.model[0]
            def load_models(self, paths, **kwargs):
                self.load_devices.append(kwargs.get('device', self.device))
                self.model.append(Component())

        diffsynth = types.ModuleType('diffsynth')
        diffsynth.ModelManager = Manager
        for name in ['WanVideoPipeline', 'CogVideoPipeline', 'HunyuanVideoPipeline',
                     'SDImagePipeline', 'SDVideoPipeline', 'FlowMatchScheduler']:
            setattr(diffsynth, name, type(name, (), {}))
        for name in ['download_models', 'download_customized_models', 'save_video']:
            setattr(diffsynth, name, lambda *args, **kwargs: [])
        scope = types.ModuleType('modelscope')
        scope.snapshot_download = lambda *args, **kwargs: None
        cases = {
            'Wan': ['WanVideoModel'], 'Wan2': ['Wan2T2VModel', 'Wan2I2VModel'],
            'Hunyuan': ['HunyuanVideoModel', 'HunyuanImageToVideoModel'],
            'CogVideo': ['CogVideoModel'], 'AnimateDiff': ['AnimateDiffModel'],
        }
        recipes = ['none', 'int8']
        with patch.dict(sys.modules, {'diffsynth': diffsynth, 'modelscope': scope}):
            for filename, classes in cases.items():
                path = Path(__file__).resolve().parents[1] / 'extensions/Video/ssui_video' / (filename + '.py')
                spec = importlib.util.spec_from_file_location('ssui_video._memory_test_' + filename, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for classname in classes:
                    # CogVideo/AnimateDiff load directly on the selected device
                    # only when neither quantization nor offload needs CPU staging.
                    devices = ('cpu', 'cuda', 'mps') if filename in ('CogVideo', 'AnimateDiff') else ('cpu',)
                    for device in devices:
                        with patch('backend.util.devices.TorchDevice.choose_torch_device', return_value=torch.device(device)):
                            for quantization in recipes:
                                for offload in [False, True]:
                                    with self.subTest(model=classname, quantization=quantization, offload=offload, device=device):
                                        cls = getattr(module, classname)
                                        load = cls if classname == 'AnimateDiffModel' else cls.load
                                        loaded = load(quantization=quantization, cpu_offload=offload)
                                        manager = loaded.model_manager
                                        self.assertEqual(manager.memory_options, ModelMemoryOptions(quantization, offload))
                                        expected_load_device = device if filename in ('CogVideo', 'AnimateDiff') and quantization == 'none' and not offload else 'cpu'
                                        self.assertEqual(manager.load_devices, [expected_load_device] * len(manager.load_devices))
                                        self.assertTrue(all(m.moves[-1] == ('cpu' if offload else str(manager.device)) for m in manager.model))
                                        if quantization == 'int8':
                                            self.assertTrue(all(m._ssui_int8 for m in manager.model))

    def test_pipeline_failure_unloads_stages(self):
        from ssui.model_memory import run_pipeline
        class Pipeline:
            cpu_offload = True
            def __init__(self):
                self.unloaded = False
            def __call__(self):
                raise RuntimeError('inference failure')
            def load_models_to_device(self, names):
                self.unloaded = names == []
        pipe = Pipeline()
        with self.assertRaisesRegex(RuntimeError, 'inference failure'):
            run_pipeline(pipe)
        self.assertTrue(pipe.unloaded)


class ImageMemoryIntegrationTest(unittest.TestCase):
    def test_quantized_lora_sidecar_restores_original_output(self):
        from backend.model_manager.load.model_cache.torch_module_autocast.torch_module_autocast import apply_custom_layers_to_model
        from backend.patches.layer_patcher import LayerPatcher
        from backend.patches.layers.lora_layer import LoRALayer
        from backend.patches.model_patch_raw import ModelPatchRaw
        model = torch.nn.Sequential(torch.nn.Linear(64, 64)).eval()
        ModelMemoryOptions('int8').quantize(model)
        apply_custom_layers_to_model(model)
        x = torch.randn(1, 64)
        original = model(x)
        up, down = torch.randn(64, 2) * .01, torch.randn(2, 64) * .01
        lora = ModelPatchRaw({'0': LoRALayer(up, None, down, 2, None)})
        with LayerPatcher.apply_smart_model_patches(
            model, [(lora, 1)], prefix='', dtype=torch.float32, force_direct_patching=True
        ):
            residual = torch.nn.functional.linear(torch.nn.functional.linear(x, down), up)
            torch.testing.assert_close(model(x), original + residual)
        torch.testing.assert_close(model(x), original)

    def test_image_cache_offloads_only_after_final_unlock(self):
        from backend.model_manager.load.model_cache.model_cache import ModelCache
        cache = ModelCache(
            execution_device_working_mem_gb=0, enable_partial_loading=False,
            keep_ram_copy_of_weights=True, execution_device=torch.device('cpu'),
            model_transform=ModelMemoryOptions('int8').quantize, offload_on_unlock=True,
        )
        cache.put('test', model=torch.nn.Sequential(torch.nn.Linear(64, 64)))
        entry = cache.get('test')
        self.assertTrue(entry.cached_model.model._ssui_int8)
        cache.lock(entry, None)
        cache.lock(entry, None)
        entry.cached_model.full_load_to_vram()  # Actual compute device is CPU here.
        with patch.object(cache, '_move_model_to_ram', wraps=cache._move_model_to_ram) as offload:
            cache.unlock(entry)
            offload.assert_not_called()
            cache.unlock(entry)
            offload.assert_called_once()
        self.assertFalse(entry.cached_model.is_in_vram())


class OtherLocalLoaderTest(unittest.TestCase):
    def test_wan22_component_policy(self):
        import sys
        import types
        from pathlib import Path

        class Pipeline(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.dit, self.dit2, self.vae = Component(), Component(), Component()
                self.vram_management_enabled = False
            @staticmethod
            def from_pretrained(**kwargs):
                return Pipeline()
            def to(self, device):
                for component in self.children():
                    component.to(device)
                return self
            def enable_vram_management(self, **kwargs):
                self.vram_management_enabled = True
                self.to('cpu')
        class Config:
            def __init__(self, **kwargs):
                pass
        pipe_module = types.ModuleType('diffsynth.pipelines.wan_video_new')
        pipe_module.WanVideoPipeline = Pipeline
        utils = types.ModuleType('diffsynth.utils')
        utils.ModelConfig = Config
        runtime = types.ModuleType('ssui_video._runtime')
        runtime.wan_runtime = lambda: {'device': 'cuda', 'torch_dtype': torch.bfloat16}
        with patch.dict(sys.modules, {'diffsynth.pipelines.wan_video_new': pipe_module, 'diffsynth.utils': utils, 'ssui_video._runtime': runtime}):
            path = Path(__file__).resolve().parents[1] / 'extensions/Video/ssui_video/Wan22.py'
            spec = importlib.util.spec_from_file_location('ssui_video._memory_test_wan22', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            recipes = ['none', 'int8']
            for cls in [module.Wan22TI2VModel, module.Wan22T2VA14BModel, module.Wan22I2VA14BModel]:
                for recipe in recipes:
                    for offload in [False, True]:
                        with self.subTest(model=cls.__name__, quantization=recipe, offload=offload):
                            model = cls.load(quantization=recipe, cpu_offload=offload)
                            self.assertEqual(model.pipe.vram_management_enabled, offload)
                            for name, component in model.pipe.named_children():
                                self.assertEqual(component.moves[-1], 'cpu' if offload else 'cuda')
                                self.assertEqual(getattr(component, '_ssui_int8', False), recipe == 'int8' and name != 'vae')

    def test_trellis_qwen_voice_public_loaders(self):
        import sys
        import types
        from pathlib import Path

        def fake_module(name, **attrs):
            result = types.ModuleType(name)
            for key, value in attrs.items():
                setattr(result, key, value)
            return result

        class Trellis:
            @staticmethod
            def from_pretrained(path, **kwargs):
                return types.SimpleNamespace(cuda=lambda: None, models={name: Component() for name in ('sparse_structure_flow_model', 'slat_flow_model', 'image_cond_model')})
        class HFModel(Component):
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return HFModel()
        class Tokenizer:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return Tokenizer()
        class Voice:
            def __init__(self, *args, **kwargs):
                self.model = types.SimpleNamespace(llm=Component(), flow=Component(), hift=Component(), device='cpu')

        modules = {
            'trellis.pipelines.trellis_image_to_3d': fake_module('trellis.pipelines.trellis_image_to_3d', TrellisImageTo3DPipeline=Trellis),
            'trellis.utils': fake_module('trellis.utils', postprocessing_utils=object()),
            'transformers': fake_module('transformers', AutoModelForCausalLM=HFModel, AutoTokenizer=Tokenizer),
            'transformers.generation': fake_module('transformers.generation', GenerationConfig=object),
            'cosyvoice.cli.cosyvoice': fake_module('cosyvoice.cli.cosyvoice', CosyVoice2=Voice),
            'cosyvoice.utils.file_utils': fake_module('cosyvoice.utils.file_utils', load_wav=lambda *args: None),
            'torchaudio': fake_module('torchaudio'),
        }
        cases = [
            ('3D-Model/ssui_3dmodel/Trellis.py', 'TrellisModel', lambda m: list(m.model.models.values())),
            ('LLM/ssui_llm/Qwen.py', 'QwenModel', lambda m: [m.model]),
            ('Voice/ssui_voice/Cosyvoice.py', 'CosyVoiceModel', lambda m: [m.model.model.llm, m.model.model.flow, m.model.model.hift]),
        ]
        recipes = ['none', 'int8']
        with patch.dict(sys.modules, modules), patch('torch.cuda.is_available', return_value=True), patch('torch.version.hip', None), patch('backend.util.devices.TorchDevice.choose_torch_device', return_value=torch.device('cpu')):
            for filename, classname, components in cases:
                path = Path(__file__).resolve().parents[1] / 'extensions' / filename
                spec = importlib.util.spec_from_file_location('memory_test_' + classname, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for recipe in recipes:
                    for offload in [False, True]:
                        with self.subTest(model=classname, quantization=recipe, offload=offload):
                            model = getattr(module, classname).load('local-test', quantization=recipe, cpu_offload=offload)
                            for component in components(model):
                                self.assertEqual(getattr(component, '_ssui_int8', False), recipe == 'int8')
                                self.assertEqual(getattr(component, '_ssui_cpu_offload', False), offload)


if __name__ == '__main__':
    unittest.main()
