import sys
import types
import unittest
from unittest.mock import patch

from PIL import Image as PILImage
from ssui.base import Image, Mesh
from ssui.config import SSUIConfig
from tests.pixal3d_test import _remove_trellis_test_stubs
from tests.utils import add_extension_paths


class Other3DWorkflowTest(unittest.TestCase):
    def setUp(self):
        add_extension_paths()
        self.saved = _remove_trellis_test_stubs()

    def tearDown(self):
        if self.saved:
            for name in list(sys.modules):
                if name == 'ssui_3dmodel' or name.startswith('ssui_3dmodel.'):
                    sys.modules.pop(name, None)
            sys.modules.update(self.saved)

    def test_prepare_does_not_load_weights(self):
        from pathlib import Path
        from ss_executor.loader import SSLoader
        from ssui_3dmodel.Trellis import TrellisModel
        from ssui_3dmodel.Trellis2 import Trellis2Model

        for name, model, node in [('trellis', TrellisModel, 'Generate TRELLIS Model'),
                                  ('trellis2', Trellis2Model, 'Generate TRELLIS.2 Model')]:
            with self.subTest(name=name), patch.object(model, 'load', side_effect=AssertionError('loaded during prepare')):
                loader = SSLoader()
                loader.load(str(Path(__file__).resolve().parents[1] / f'examples/advance/workflow-{name}.py'))
                loader.Execute()
                self.assertIn('seed', loader.GetConfig(f'img2mesh_{name}')[node])

    def test_trellis2_preserves_mask_and_maps_export_settings(self):
        from ssui_3dmodel.Trellis2 import Trellis2Model, GenTrellis2Model
        from unittest.mock import Mock

        source = PILImage.new('RGBA', (8, 8), (10, 20, 30, 128))
        generated = types.SimpleNamespace(vertices=object(), faces=object(), attrs=object(), coords=object())
        pipeline = Mock(pbr_attr_layout={'base_color': slice(0, 3)})
        pipeline.run.return_value = ([generated], (None, None, 512))
        exporter = Mock(return_value=object())
        config = SSUIConfig()
        config.set_prepared(False)
        controls = config('mesh')
        controls['resolution'] = 512
        controls['shape_steps'] = 7
        controls['texture_size'] = 1024
        controls['export_mode'] = 'pbr_texture'
        with patch.dict(sys.modules, {'o_voxel': types.SimpleNamespace(postprocess=types.SimpleNamespace(to_glb=exporter))}):
            result = GenTrellis2Model(controls, Trellis2Model('local', pipeline), Image(source))
        self.assertIsInstance(result, Mesh)
        self.assertIs(pipeline.run.call_args.args[0], source)
        self.assertEqual(pipeline.run.call_args.kwargs['pipeline_type'], '512')
        self.assertEqual(pipeline.run.call_args.kwargs['shape_slat_sampler_params'], {'steps': 7})
        self.assertEqual(exporter.call_args.kwargs['texture_size'], 1024)
        self.assertIs(exporter.call_args.kwargs['attr_volume'], generated.attrs)

    def test_descriptor_imports_unloaded_submodule(self):
        import tempfile
        from pathlib import Path
        from ss_executor.__main__ import convert_task_param

        # A real temporary package ensures this tests import behavior, rather than an attribute stub.
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'ssui_descriptor_fixture'
            package.mkdir()
            (package / '__init__.py').write_text('', encoding='utf-8')
            (package / 'loader.py').write_text('def load(value):\n    return value + 1\n', encoding='utf-8')
            sys.path.insert(0, directory)
            try:
                self.assertEqual(convert_task_param({'function': 'ssui_descriptor_fixture.loader.load',
                                                     'params': {'value': 41}}), 42)
            finally:
                sys.path.remove(directory)
                sys.modules.pop('ssui_descriptor_fixture.loader', None)
                sys.modules.pop('ssui_descriptor_fixture', None)

    def test_trellis_vertex_colors_export_without_gaussian_renderer(self):
        import torch
        from unittest.mock import Mock
        from ssui_3dmodel.Trellis import TrellisModel, GenModel

        generated = types.SimpleNamespace(success=True,
            vertices=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]),
            faces=torch.tensor([[0, 1, 2]]), vertex_attrs=torch.tensor([[1., 0., 0.]] * 3))
        pipeline = Mock()
        pipeline.run.return_value = {'mesh': [generated]}
        config = SSUIConfig()
        config.set_prepared(False)
        controls = config('mesh')
        controls['export_mode'] = 'vertex_colors'
        result = GenModel(controls, TrellisModel('local', pipeline), Image(PILImage.new('RGBA', (8, 8))))
        self.assertEqual(pipeline.run.call_args.kwargs['formats'], ['mesh'])
        self.assertEqual(result._model.visual.kind, 'vertex')
        self.assertEqual(result._model.export(file_type='glb')[:4], b'glTF')

    def test_trellis2_vertex_colors_skip_uv_export(self):
        import torch
        from unittest.mock import Mock
        from ssui_3dmodel.Trellis2 import Trellis2Model, GenTrellis2Model

        generated = types.SimpleNamespace(vertices=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]),
            faces=torch.tensor([[0, 1, 2]]), query_vertex_attrs=lambda: torch.tensor([[1., 0., 0., 0., 1., 1.]] * 3))
        pipeline = Mock(pbr_attr_layout={'base_color': slice(0, 3)})
        pipeline.run.return_value = ([generated], (None, None, 512))
        config = SSUIConfig()
        config.set_prepared(False)
        result = GenTrellis2Model(config('mesh'), Trellis2Model('local', pipeline), Image(PILImage.new('RGBA', (8, 8))))
        self.assertEqual(result._model.visual.kind, 'vertex')
        self.assertEqual(result._model.export(file_type='glb')[:4], b'glTF')
