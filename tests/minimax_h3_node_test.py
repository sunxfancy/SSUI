import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage

from ssui import Image, Prompt, Video
from ssui_video import MiniMaxH3


class _Config(dict):
    def is_prepare(self):
        return False


class _CompletedProcess:
    returncode = 0
    stdout = []

    def wait(self):
        return 0


class TestMiniMaxH3Node(unittest.TestCase):
    def _config(self, quantization="nf4"):
        return _Config(
            quantization=quantization,
            num_frames=124,
            num_inference_steps=1,
            height=256,
            width=448,
            seed=7,
        )

    def test_nf4_uses_dedicated_runner_and_keeps_audio_container(self):
        with tempfile.TemporaryDirectory() as root, patch.object(
            MiniMaxH3, "H3_PYTHON", "h3-python"
        ), patch.object(
            MiniMaxH3, "H3_NF4_MODEL_ROOT", "nf4-models"
        ), patch.object(
            MiniMaxH3, "H3_DIFFSYNTH_ROOT", "diffsynth-main"
        ), patch.object(
            MiniMaxH3.subprocess, "Popen"
        ) as popen:
            original_cwd = os.getcwd()
            os.chdir(root)
            try:
                def create_output(command, **_kwargs):
                    output = Path(command[command.index("--output") + 1])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"mp4")
                    return _CompletedProcess()

                popen.side_effect = create_output
                result = MiniMaxH3._run_h3(
                    self._config(), "t2va", Prompt("a speaking robot")
                )
            finally:
                os.chdir(original_cwd)

        command = popen.call_args.args[0]
        self.assertIsInstance(result, Video)
        self.assertTrue(result.path.endswith(".mp4"))
        self.assertEqual(result.metadata, {"audio": True})
        self.assertEqual(command[1], MiniMaxH3.H3_NF4_RUNNER)
        self.assertIn("--model-root", command)
        self.assertIn("nf4-models", command)
        self.assertIn("--diffsynth-root", command)
        self.assertNotIn("--quantization", command)

    def test_fl2va_passes_first_and_last_keyframes(self):
        first = Image(PILImage.new("RGB", (32, 32), "red"))
        last = Image(PILImage.new("RGB", (32, 32), "blue"))
        with tempfile.TemporaryDirectory() as root, patch.object(
            MiniMaxH3, "H3_PYTHON", "h3-python"
        ), patch.object(MiniMaxH3.subprocess, "Popen") as popen:
            original_cwd = os.getcwd()
            os.chdir(root)
            try:
                def create_output(command, **_kwargs):
                    output = Path(command[command.index("--output") + 1])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"mp4")
                    return _CompletedProcess()

                popen.side_effect = create_output
                MiniMaxH3._run_h3(
                    self._config(), "fl2va", Prompt("transition"), first, last
                )
            finally:
                os.chdir(original_cwd)

        command = popen.call_args.args[0]
        self.assertIn("--image", command)
        self.assertIn("--last-image", command)


if __name__ == "__main__":
    unittest.main()
