import os
import tempfile
import unittest

import torch

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestCosyVoiceModel(unittest.TestCase):
    def test_cosyvoice(self):
        from cosyvoice.cli.cosyvoice import CosyVoice2

        import torchaudio

        download_if_needed("cosyvoice")
        cosyvoice = CosyVoice2(
            "iic/CosyVoice2-0.5B", load_jit=False, load_trt=False, fp16=False
        )
        prompt_speech_16k = torch.zeros(16000, dtype=torch.float32)

        assert cosyvoice.add_zero_shot_spk("你好", prompt_speech_16k, "my_spk") is True

        with tempfile.TemporaryDirectory() as tmp:
            saved = 0
            for i, chunk in enumerate(
                cosyvoice.inference_zero_shot(
                    "收到好友从远方寄来的生日礼物。",
                    "希望你以后能够做的比我还好呦。",
                    prompt_speech_16k,
                    stream=False,
                )
            ):
                torchaudio.save(
                    os.path.join(tmp, f"zero_shot_{i}.wav"),
                    chunk["tts_speech"],
                    cosyvoice.sample_rate,
                )
                saved += 1
                if saved >= 2:
                    break
            self.assertGreaterEqual(saved, 1)
