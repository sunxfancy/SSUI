from typing import Optional, List, Union, Generator
import torch
import torchaudio
from ssui.config import SSUIConfig
from ssui.base import Audio
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider
from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.file_utils import load_wav

class CosyVoiceModel:
    def __init__(
        self,
        model_path: str = "",
        model: Optional[CosyVoice2] = None,
    ):
        self.model_path = model_path
        self.model = model

    def getModel(self):
        return self.model

    @staticmethod
    def load(model_path: str):
        model = CosyVoice2(model_path, load_jit=False, load_trt=False, fp16=False)
        return CosyVoiceModel(model_path, model)

@param("seed", Random(), default=42)
@param("use_zero_shot", Switch(), default=True)
@param("zero_shot_prompt", Switch(), default=True)
@param("speaker_id", Slider(0, 100, 1), default=0)
def GenVoice(
    config: SSUIConfig,
    model: CosyVoiceModel,
    text: str,
    prompt_audio: Optional[Audio] = None,
):
    if config.is_prepare():
        return Audio()

    print("GenVoice executed")
    print("seed:", config["seed"])
    print("use_zero_shot:", config["use_zero_shot"])
    print("zero_shot_prompt:", config["zero_shot_prompt"])
    print("speaker_id:", config["speaker_id"])

    # Convert prompt audio to the required format if provided
    prompt_speech_16k = None
    if prompt_audio and config["zero_shot_prompt"]:
        prompt_speech_16k = load_wav(prompt_audio.path, 16000)

    # Generate audio based on configuration
    if config["use_zero_shot"]:
        if prompt_speech_16k:
            # Use zero-shot with prompt
            outputs = model.getModel().inference_zero_shot(
                text,
                f"Speaker {config['speaker_id']}",
                prompt_speech_16k,
                stream=False
            )
        else:
            # Use zero-shot without prompt
            outputs = model.getModel().inference_zero_shot(
                text,
                "",
                "",
                zero_shot_spk_id=f"speaker_{config['speaker_id']}",
                stream=False
            )
    else:
        # Use cross-lingual inference
        outputs = model.getModel().inference_cross_lingual(
            text,
            prompt_speech_16k if prompt_speech_16k else None,
            stream=False
        )

    # Get the first output audio
    output_audio = next(outputs)['tts_speech']
    
    return Audio(output_audio, sample_rate=model.getModel().sample_rate)
