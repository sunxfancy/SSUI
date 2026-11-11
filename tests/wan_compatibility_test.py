"""Run numerical model/pipeline compatibility checks in a clean interpreter."""
from pathlib import Path
import subprocess
import sys
import unittest


class WanCompatibilityTest(unittest.TestCase):
    def test_single_and_batched_latents_match_direct_model(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import torch
from tests.utils import add_extension_paths
add_extension_paths()
from diffsynth.models.wan_video_dit import WanModel
from diffsynth.pipelines.wan_video import model_fn_wan_video
model = WanModel(dim=32, in_dim=4, ffn_dim=64, out_dim=4, text_dim=8,
                 freq_dim=16, eps=1e-6, patch_size=(1,2,2), num_heads=4,
                 num_layers=1, has_image_input=False).eval()
for batch in (1,2):
    x=torch.randn(batch,4,2,4,4)
    timestep=torch.ones(batch)
    context=torch.randn(batch,3,8)
    with torch.no_grad():
        direct=model(x,timestep,context)
        piped=model_fn_wan_video(model,x=x,timestep=timestep,context=context)
    assert direct.shape==x.shape
    torch.testing.assert_close(direct,piped)
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=root,
                                text=True, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
