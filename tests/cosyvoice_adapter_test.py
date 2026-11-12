"""Exercise the SSUI Audio boundary without model downloads."""
import io
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import soundfile as sf
import torch


class TestCosyVoiceAdapter(unittest.TestCase):
    def generate(self, outputs, prompt_text='参考语音。', use_zero_shot=True, path=None, text_frontend=True):
        from ssui_voice.Cosyvoice import CosyVoiceModel, GenVoice
        from ssui.base import Audio
        buffer = io.BytesIO()
        sf.write(buffer, np.ones(16000, dtype=np.float32) * 0.1, 16000, format='WAV')
        class Config(dict):
            def is_prepare(self):
                return False
        config = Config(seed=42, use_zero_shot=use_zero_shot, zero_shot_prompt=True, speaker_id=0)
        with patch('ssui_voice.Cosyvoice.torchaudio.load', return_value=(torch.ones(1, 16000), 16000)) as load:
            result = GenVoice(config, CosyVoiceModel(model=outputs), '测试。', Audio('wav', buffer.getvalue(), path=path), prompt_text, text_frontend=text_frontend)
            if path:
                self.assertEqual(load.call_args.args[0], path)
            return result

    def test_preserves_all_chunks_and_returns_serialized_audio(self):
        from unittest.mock import Mock
        model = Mock(sample_rate=24000)
        model.inference_zero_shot.return_value = iter([{'tts_speech': torch.ones(1, 100) * .2},
                                                     {'tts_speech': torch.ones(1, 200) * .3}])
        result = self.generate(model)
        audio, rate = sf.read(io.BytesIO(result._audio))
        self.assertEqual((len(audio), rate, result._format), (300, 24000, 'wav'))
        self.assertEqual(model.inference_zero_shot.call_args.args[1], '参考语音。')
        self.assertEqual(result._text, '测试。')

    def test_requires_reference_transcript(self):
        with self.assertRaisesRegex(ValueError, 'transcript'):
            self.generate(SimpleNamespace(), prompt_text='')

    def test_rejects_empty_output(self):
        from unittest.mock import Mock
        model = Mock(sample_rate=24000)
        model.inference_zero_shot.return_value = iter([])
        with self.assertRaisesRegex(RuntimeError, 'no audio'):
            self.generate(model)

    def test_path_backed_prompt_and_explicit_normalization_bypass(self):
        from unittest.mock import Mock
        model = Mock(sample_rate=24000)
        model.inference_zero_shot.return_value = iter([{'tts_speech': torch.ones(1, 100) * .2}])
        self.generate(model, path='/reference.wav', text_frontend=False)
        self.assertFalse(model.inference_zero_shot.call_args.kwargs['text_frontend'])

    def test_load_preserves_opt_in_memory_controls(self):
        from ssui_voice.Cosyvoice import CosyVoiceModel
        with patch('ssui_voice.Cosyvoice.CosyVoice2') as factory, patch('ssui_voice.Cosyvoice.ModelMemoryOptions') as options:
            CosyVoiceModel.load('/model')
            options.return_value.configure.assert_not_called()
            CosyVoiceModel.load('/model', quantization='int8', cpu_offload=True)
            options.assert_called_with('int8', True)
            runtime = factory.return_value.model
            options.return_value.configure.assert_called_once_with([runtime.llm, runtime.flow, runtime.hift], device=runtime.device)
