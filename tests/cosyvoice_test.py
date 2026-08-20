import os
import sys
import tempfile
import types
import unittest

import torch

from tests.fakes.audio import FakeCosyVoice


def _install_cosyvoice_stubs():
    """向 sys.modules 注入 cosyvoice 假模块。

    vendored cosyvoice 依赖 hyperpyyaml 等未随 SSUI 安装的包；
    这里用假模块替代，只验证下游推理接口的契约。
    """
    if "cosyvoice.cli.cosyvoice" in sys.modules:
        return
    root = types.ModuleType("cosyvoice")
    root.__path__ = []
    cli = types.ModuleType("cosyvoice.cli")
    cli.__path__ = []
    cli_module = types.ModuleType("cosyvoice.cli.cosyvoice")
    cli_module.CosyVoice2 = FakeCosyVoice
    utils = types.ModuleType("cosyvoice.utils")
    utils.__path__ = []
    file_utils = types.ModuleType("cosyvoice.utils.file_utils")
    file_utils.load_wav = lambda *args, **kwargs: torch.zeros(16000)
    sys.modules.update(
        {
            "cosyvoice": root,
            "cosyvoice.cli": cli,
            "cosyvoice.cli.cosyvoice": cli_module,
            "cosyvoice.utils": utils,
            "cosyvoice.utils.file_utils": file_utils,
        }
    )


_install_cosyvoice_stubs()


class TestCosyVoiceWorkflow(unittest.TestCase):
    """给定假 CosyVoice 输出，验证推理接口能跑通并保存音频。"""

    def test_cosyvoice(self):
        from cosyvoice.cli import cosyvoice as cosyvoice_cli
        from cosyvoice.utils.file_utils import load_wav

        import torchaudio

        tmp_dir = tempfile.mkdtemp()
        cosyvoice = cosyvoice_cli.CosyVoice2("fake/repo", load_jit=False, load_trt=False, fp16=False)
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
