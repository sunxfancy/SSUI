"""TorchAudio 2.9 output compatibility, without TorchCodec or model weights."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile
import torch

from backend.util.audio import write_audio


class AudioCompatibilityTest(unittest.TestCase):
    def test_tensor_channels_and_sample_rate_survive_export(self):
        audio = torch.stack((torch.full((64,), 0.25), torch.full((64,), -0.5))).to(torch.bfloat16)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            write_audio(path, audio, 24000)
            samples, rate = soundfile.read(path, always_2d=True)
        self.assertEqual(rate, 24000)
        self.assertEqual(samples.shape, (64, 2))
        np.testing.assert_allclose(samples[:, 0], 0.25, atol=1e-4)
        np.testing.assert_allclose(samples[:, 1], -0.5, atol=1e-4)

    def test_numpy_mono_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            write_audio(path, np.zeros(32, dtype=np.float32), 16000)
            samples, rate = soundfile.read(path)
        self.assertEqual(rate, 16000)
        self.assertEqual(samples.shape, (32,))
