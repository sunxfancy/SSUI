import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.utils import get_test_data_dir, should_run_model_tests, model_output_dir


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestCosyVoiceModel(unittest.TestCase):
    def test_cosyvoice(self):
        # Exercise the public adapter with real reference audio and transcript.
        root = Path(__file__).resolve().parents[2]
        model_dir = os.environ.get("SSUI_COSYVOICE_MODEL_DIR", str(get_test_data_dir() / "cosyvoice"))
        with model_output_dir("cosyvoice") as output:
            command = [sys.executable, str(root / "scripts/probe_cosyvoice.py"),
                       "--model-dir", model_dir, "--output-dir", str(output), "--download"]
            if os.environ.get("SSUI_COSYVOICE_REQUIRE_ROCM") == "1":
                command.append("--require-rocm")
            if os.environ.get("SSUI_COSYVOICE_PROMPT"):
                command.extend(["--prompt", os.environ["SSUI_COSYVOICE_PROMPT"]])
            subprocess.run(command, cwd=root, check=True, timeout=900)
            report = json.loads((Path(output) / "zero_shot.json").read_text(encoding="utf-8"))
            self.assertEqual(report["sample_rate"], 24000)
            self.assertGreater(report["audio_seconds"], 1)
            self.assertGreater(report["rms"], 0)
            self.assertTrue(Path(report["output"]).is_file())
