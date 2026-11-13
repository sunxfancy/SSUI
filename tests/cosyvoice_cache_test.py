"""Check incremental Qwen attention against full-prefix decoding on CPU."""
import subprocess
import sys
import unittest
from pathlib import Path


class TestCosyVoiceCache(unittest.TestCase):
    def test_cached_decoding_matches_full_prefix(self):
        # Other contract suites replace Transformers in sys.modules. Use an
        # isolated interpreter to exercise the actual installed library.
        code = '''
import torch
torch.set_num_threads(2)
from tests.utils import add_extension_paths
add_extension_paths()
from transformers import Qwen2Config, Qwen2ForCausalLM
from cosyvoice.llm.llm import Qwen2Encoder
torch.manual_seed(7)
cfg = Qwen2Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                  num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
cfg._attn_implementation = 'eager'
encoder = Qwen2Encoder.__new__(Qwen2Encoder)
torch.nn.Module.__init__(encoder)
encoder.model = Qwen2ForCausalLM(cfg).eval()
x = torch.randn(1, 5, 16)
with torch.inference_mode():
    full, _ = encoder.forward_one_step(x, torch.ones(1, 5, 5, dtype=torch.bool).tril())
    _, cache = encoder.forward_one_step(x[:, :4], torch.ones(1, 4, 4, dtype=torch.bool).tril())
    step, _ = encoder.forward_one_step(x[:, 4:], torch.ones(1, 1, 1, dtype=torch.bool), cache)
torch.testing.assert_close(step[:, -1], full[:, -1], atol=1e-5, rtol=1e-5)
'''
        result = subprocess.run([sys.executable, "-c", code],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
