"""SSUI adapter contracts, independent of model downloads and fake model tests."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import torch
from ssui.base import Audio
from ssui.config import SSUIConfig


class TestCosyVoiceAdapter(unittest.TestCase):
    def setUp(self):
        cli = types.ModuleType("cosyvoice.cli.cosyvoice")
        cli.CosyVoice2 = Mock()
        files = types.ModuleType("cosyvoice.utils.file_utils")
        self.reference = torch.ones(1, 32000)
        files.load_wav = Mock(return_value=self.reference)
        path = Path(__file__).resolve().parents[1] / "extensions/Voice/ssui_voice/Cosyvoice.py"
        spec = importlib.util.spec_from_file_location("cosyvoice_adapter_contract", path)
        self.adapter = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {cli.__name__: cli, files.__name__: files}):
            spec.loader.exec_module(self.adapter)
        self.engine = Mock(sample_rate=24000)
        self.engine.frontend.spk2info = {}
        self.engine.inference_zero_shot.return_value = iter([
            {"tts_speech": torch.ones(1, 20)}, {"tts_speech": torch.full((1, 30), 2.)}])
        self.engine.inference_cross_lingual.return_value = iter([{"tts_speech": torch.ones(1, 40)}])
        self.model = self.adapter.CosyVoiceModel("test", self.engine)
        self.config = SSUIConfig()("voice")

    def test_reference_transcript_and_all_sentence_chunks(self):
        result = self.adapter.GenVoice(self.config, self.model, "两句。测试。", Audio.load("ref.wav"), "原文")
        self.engine.inference_zero_shot.assert_called_once_with("两句。测试。", "原文", self.reference, stream=False)
        self.assertEqual(result.sample_rate, 24000)
        self.assertEqual(result._audio.shape, (1, 50))
        self.assertTrue(torch.equal(result._audio[:, 20:], torch.full((1, 30), 2.)))

    def test_reference_requires_transcript(self):
        with self.assertRaisesRegex(ValueError, "transcript"):
            self.adapter.GenVoice(self.config, self.model, "测试", Audio.load("ref.wav"))
        self.engine.inference_zero_shot.assert_not_called()

    def test_missing_reference_requires_registered_speaker(self):
        with self.assertRaisesRegex(ValueError, "register"):
            self.adapter.GenVoice(self.config, self.model, "测试")
        self.engine.frontend.spk2info["speaker_0"] = {}
        self.adapter.GenVoice(self.config, self.model, "测试")
        self.engine.inference_zero_shot.assert_called_once_with("测试", "", "", zero_shot_spk_id="speaker_0", stream=False)

    def test_cross_lingual_accepts_audio_tensor_without_boolean_conversion(self):
        self.config["use_zero_shot"] = False
        result = self.adapter.GenVoice(self.config, self.model, "Hello", Audio.load("ref.wav"))
        self.engine.inference_cross_lingual.assert_called_once_with("Hello", self.reference, stream=False)
        self.assertEqual(result._audio.shape[-1], 40)

    def test_cross_lingual_requires_reference(self):
        self.config["use_zero_shot"] = False
        with self.assertRaisesRegex(ValueError, "reference audio"):
            self.adapter.GenVoice(self.config, self.model, "Hello")

    def test_empty_model_output_fails(self):
        self.engine.inference_cross_lingual.return_value = iter([])
        self.config["use_zero_shot"] = False
        with self.assertRaisesRegex(RuntimeError, "no audio"):
            self.adapter.GenVoice(self.config, self.model, "Hello", Audio.load("ref.wav"))
