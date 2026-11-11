"""Real AnimateDiff node regression in a process isolated from workflow stubs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.utils import get_test_data_dir, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestDiffSynthModel(unittest.TestCase):
    def test_diffsynth(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as output:
            subprocess.run(
                [sys.executable, str(root / "scripts/video_smoke.py"),
                 "--model-dir", os.environ.get("SSUI_VIDEO_MODEL_DIR", str(get_test_data_dir() / "diffsynth")),
                 "--output", output, "--size", "64", "--frames", "4", "--steps", "2"],
                cwd=root, check=True, timeout=1800, env=dict(os.environ),
            )
            self.assertTrue((Path(output) / "animatediff.mp4").is_file())
            self.assertTrue((Path(output) / "report.json").is_file())
