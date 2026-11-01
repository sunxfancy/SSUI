"""Portable 3D geometry and MPS interpolation regressions without model downloads."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class MeshRuntimeTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('SSUI_RUN_3D_RUNTIME_TESTS') == '1', 'opt-in real 3D runtime')
    def test_geometry_and_workflow_prepare(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import torch
import trimesh
from tsr.models.isosurface import MarchingCubeHelper
from tsr.models.tokenizers.image import PortableViTEmbeddings
from transformers import ViTConfig
from ss_executor.loader import SSLoader
helper = MarchingCubeHelper(32)
center = torch.tensor([0.3, 0.5, 0.65])
field = (helper.grid_vertices - center).square().sum(-1) - 0.15**2
vertices, faces = helper(field)
# An asymmetric center detects incorrect x/z swaps from torchmcubes conventions.
assert torch.max(torch.abs(vertices.mean(0) - center)) < 0.02
mesh = trimesh.Trimesh(vertices.numpy(), faces.numpy())
assert mesh.is_watertight and len(mesh.faces) > 0
if torch.backends.mps.is_available():
    config = ViTConfig(image_size=32, patch_size=8, hidden_size=16, num_attention_heads=2)
    embed = PortableViTEmbeddings(config)
    x = torch.zeros(1, 65, 16)
    expected = embed.interpolate_pos_encoding(x, 64, 64)
    actual = embed.to('mps').interpolate_pos_encoding(x.to('mps'), 64, 64)
    torch.testing.assert_close(actual.cpu(), expected)
loader = SSLoader()
loader.load('examples/advance/workflow-3d-mac.py')
loader.Execute()
loader.GetConfig('img2mesh_mac')
'''
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join(map(str, [root, root/'extensions/3D-Model', root/'extensions/3D-Model/vendor']))
        result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
