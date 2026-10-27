"""Validate the low-memory UMT5 execution against the original encoder."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class WanMacTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('SSUI_RUN_VIDEO_RUNTIME_TESTS') == '1', 'opt-in real Torch runtime')
    def test_staged_text_encoding_matches_original(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import torch
from diffsynth.models.wan_video_text_encoder import WanTextEncoder
from diffsynth.models.utils import init_weights_on_device
from scripts.wan_mac_smoke import finite
if torch.backends.mps.is_available():
    good = torch.ones((1, 16, 3, 16, 16), device='mps')
    finite(good, 'five-dimensional latent')
    good[0, 0, 0, 0, 0] = float('nan')
    try:
        finite(good, 'invalid latent')
    except RuntimeError:
        pass
    else:
        raise AssertionError('NaN was accepted')
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as folder, torch.inference_mode():
    torch.manual_seed(42)
    original = WanTextEncoder(vocab=32, dim=16, dim_attn=16, dim_ffn=32, num_heads=2, num_layers=2).eval()
    ids = torch.tensor([[1,2,3,0], [4,5,0,0]])
    mask = ids.ne(0).long()
    expected = original(ids, mask)
    path = Path(folder) / 'encoder.pth'
    torch.save(original.state_dict(), path)
    with init_weights_on_device():
        staged = WanTextEncoder(vocab=32, dim=16, dim_attn=16, dim_ffn=32, num_heads=2, num_layers=2)
    staged.load_state_dict(torch.load(path, weights_only=True, mmap=True), assign=True)
    staged.eval()
    x = staged.token_embedding(ids)
    staged.token_embedding.to('meta')
    for block in staged.blocks:
        x = block(x, mask, pos_bias=None)
        block.to('meta')
    x = staged.norm(x)
    torch.testing.assert_close(x, expected)
    assert all(p.is_meta for b in staged.blocks for p in b.parameters())
'''
        env = dict(os.environ, PYTHONPATH=str(root / 'extensions/Video') + os.pathsep + str(root))
        result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
