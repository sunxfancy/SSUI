import os
import tempfile
import unittest
from unittest.mock import patch

import torch

from tests.fakes.audio import FakeCosyVoice


class TestCosyVoiceWorkflow(unittest.TestCase):
    """给定假 CosyVoice 输出，验证推理接口能跑通并保存音频。"""

    @patch("cosyvoice.cli.cosyvoice.CosyVoice2", FakeCosyVoice)
    @patch("cosyvoice.utils.file_utils.load_wav", lambda *args, **kwargs: torch.zeros(16000))
    def test_cosyvoice(self):
        from cosyvoice.cli.cosyvoice import CosyVoice2
        from cosyvoice.utils.file_utils import load_wav

        import torchaudio

        tmp_dir = tempfile.mkdtemp()
        cosyvoice = CosyVoice2("fake/repo", load_jit=False, load_trt=False, fp16=False)
        prompt_speech_16k = load_wav("./fake_prompt.wav", 16000)

        assert cosyvoice.add_zero_shot_spk("你好", prompt_speech_16k, "my_spk") is True

        saved = []
        for i, chunk in enumerate(
            cosyvoice.inference_zero_shot("测试文本", "希望做得好", prompt_speech_16k, stream=False)
        ):
            path = os.path.join(tmp_dir, f"zero_shot_{i}.wav")
            torchaudio.save(path, chunk["tts_speech"], cosyvoice.sample_rate)
            saved.append(path)

        for i, chunk in enumerate(
            cosyvoice.inference_cross_lingual("他说[laughter]停下来了", prompt_speech_16k, stream=False)
        ):
            path = os.path.join(tmp_dir, f"cross_lingual_{i}.wav")
            torchaudio.save(path, chunk["tts_speech"], cosyvoice.sample_rate)
            saved.append(path)

        for i, chunk in enumerate(
            cosyvoice.inference_instruct2("用四川话说这句话", prompt_speech_16k, stream=False)
        ):
            path = os.path.join(tmp_dir, f"instruct_{i}.wav")
            torchaudio.save(path, chunk["tts_speech"], cosyvoice.sample_rate)
            saved.append(path)

        self.assertGreaterEqual(len(saved), 3)
        for path in saved:
            self.assertTrue(os.path.exists(path))
