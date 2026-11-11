import os
from pathlib import Path
import subprocess
import sys
import unittest
from urllib.request import urlretrieve

from tests.utils import get_test_data_dir, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestCosyVoiceModel(unittest.TestCase):
    def test_cosyvoice(self):
        # A fresh interpreter prevents fake CosyVoice modules installed during
        # ordinary test discovery from turning this into a mock-only test.
        root = Path(__file__).resolve().parents[2]
        artifacts = get_test_data_dir() / 'cosyvoice2-artifacts'
        artifacts.mkdir(parents=True, exist_ok=True)
        prompt = Path(os.environ.get('SSUI_COSYVOICE_PROMPT', str(artifacts / 'prompt.wav')))
        if not prompt.exists():
            urlretrieve('https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/main/asset/zero_shot_prompt.wav', prompt)
        command = [sys.executable, str(root / 'scripts/cosyvoice_smoke.py'),
                   '--prompt', str(prompt), '--prompt-text',
                   os.environ.get('SSUI_COSYVOICE_PROMPT_TEXT', '希望你以后能够做的比我还好呦。'),
                   '--device', os.environ.get('SSUI_COSYVOICE_DEVICE', 'auto'),
                   '--output', str(artifacts / 'output.wav')]
        if os.environ.get('SSUI_COSYVOICE_MODEL'):
            command += ['--model', os.environ['SSUI_COSYVOICE_MODEL']]
        subprocess.run(command, cwd=root, check=True, timeout=900)
        self.assertGreater((artifacts / 'output.wav').stat().st_size, 44)
