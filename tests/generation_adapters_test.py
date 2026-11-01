"""Check SSUI-to-model argument boundaries without installing GPU kernels."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class WrappedImage:
    def __init__(self, image=None):
        self._image = image


class WrappedMesh:
    def __init__(self, model=None):
        self._model = model


class Config(dict):
    def is_prepare(self):
        return False


def load_adapter(relative_path, extra):
    exports = {
        'torch': dict(nn=types.SimpleNamespace(Module=object), bfloat16=object()),
        'ssui.annotation': dict(param=lambda *a, **kw: lambda fn: fn),
        'ssui.base': dict(Image=WrappedImage, Mesh=WrappedMesh, Prompt=object),
        'ssui.config': dict(SSUIConfig=Config),
        'ssui.controller': dict(Random=Mock(), Slider=Mock(), Switch=Mock()),
        **extra,
    }
    modules = {}
    for name, attrs in exports.items():
        modules[name] = types.ModuleType(name)
        modules[name].__dict__.update(attrs)
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location('_generation_adapter_under_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class GenerationAdaptersTest(unittest.TestCase):
    def test_wan_keeps_frame_count_separate_from_sampling_steps(self):
        pipeline = Mock(return_value=['frame'])
        factory = Mock()
        factory.from_model_manager.return_value = pipeline
        module = load_adapter('extensions/Video/ssui_video/Wan.py', {
            'diffsynth': dict(ModelManager=object, WanVideoPipeline=factory),
            'modelscope': dict(snapshot_download=Mock()),
        })
        config = Config(num_frames=17, num_inference_steps=2, seed=42, tiled=True)
        prompt = types.SimpleNamespace(text='a walking robot')
        image = WrappedImage(object())
        result = module.WanImageTextToVideo(
            config, types.SimpleNamespace(model_manager=object()), image, prompt, prompt)
        args = pipeline.call_args.kwargs
        self.assertEqual(args['num_frames'], 17)
        self.assertEqual(args['num_inference_steps'], 2)
        self.assertIs(args['input_image'], image._image)
        self.assertEqual(result[0]._image, 'frame')

    def test_trellis_unwraps_image_before_preprocessing(self):
        exporter = Mock(return_value='mesh')
        module = load_adapter('extensions/3D-Model/ssui_3dmodel/Trellis.py', {
            'trellis.pipelines.trellis_image_to_3d': dict(TrellisImageTo3DPipeline=Mock()),
            'trellis.utils': dict(postprocessing_utils=types.SimpleNamespace(to_glb=exporter)),
        })
        pipeline = Mock()
        pipeline.run.return_value = {'gaussian': ['g'], 'mesh': ['m']}
        image = WrappedImage(object())
        config = Config(seed=7, preprocess_image=True, sparse_structure_steps=2,
                        sparse_structure_cfg=7.5, slat_steps=2, slat_cfg=3)
        result = module.GenModel(config, types.SimpleNamespace(getModel=lambda: pipeline), image)
        self.assertIs(pipeline.run.call_args.kwargs['image'], image._image)
        self.assertEqual(result._model, 'mesh')
