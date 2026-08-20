"""CosyVoice 的确定性假实现。"""

import torch


class FakeCosyVoice:
    sample_rate = 16000

    def __init__(self, *args, **kwargs):
        pass

    def add_zero_shot_spk(self, *args, **kwargs):
        return True

    def _infer(self):
        return iter(
            [{"tts_speech": torch.zeros(self.sample_rate, dtype=torch.float32)}]
        )

    def inference_zero_shot(self, *args, **kwargs):
        return self._infer()

    def inference_cross_lingual(self, *args, **kwargs):
        return self._infer()

    def inference_instruct2(self, *args, **kwargs):
        return self._infer()
