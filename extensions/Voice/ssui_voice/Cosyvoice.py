from ssui.model_memory import ModelMemoryOptions
from typing import Optional
import torch
from ssui.config import SSUIConfig
from ssui.base import Audio, Voice
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
    def load(model_path: str, *, quantization: str = "none", cpu_offload: bool = False):
        options = ModelMemoryOptions(quantization, cpu_offload)
        model = CosyVoice2(model_path, load_jit=False, load_trt=False, fp16=False)
        if quantization != "none" or cpu_offload:
            options.configure([model.model.llm, model.model.flow, model.model.hift], device=model.model.device)
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
    prompt_text: str = "",
):
    if config.is_prepare():
        return Voice()

    voice = model.getModel()
    if voice is None:
        raise ValueError("Load a CosyVoice2 model before generating speech")
    if not text.strip():
        raise ValueError("Speech text must not be empty")
    torch.manual_seed(int(config["seed"]))
    prompt_speech_16k = None
    if prompt_audio is not None and config["zero_shot_prompt"]:
        if not prompt_audio.path:
            raise ValueError("Reference audio must have a file path")
        prompt_speech_16k = load_wav(prompt_audio.path, 16000)

    speaker = f"speaker_{config['speaker_id']}"
    if config["use_zero_shot"]:
        if prompt_speech_16k is not None:
            if not prompt_text.strip():
                raise ValueError("Zero-shot synthesis requires the reference audio transcript (prompt_text)")
            outputs = voice.inference_zero_shot(
                text, prompt_text, prompt_speech_16k, stream=False)
        else:
            if speaker not in voice.frontend.spk2info:
                raise ValueError(f"Provide reference audio and prompt_text, or register {speaker} first")
            outputs = voice.inference_zero_shot(
                text, "", "", zero_shot_spk_id=speaker, stream=False)
    else:
        if prompt_speech_16k is None:
            raise ValueError("Cross-lingual synthesis requires reference audio")
        outputs = voice.inference_cross_lingual(text, prompt_speech_16k, stream=False)

    # CosyVoice yields one chunk for each normalized sentence, even without streaming.
    chunks = [chunk['tts_speech'].detach().cpu() for chunk in outputs]
    if not chunks:
        raise RuntimeError("CosyVoice2 generated no audio")
    return Voice(audio=torch.cat(chunks, dim=-1), fps=voice.sample_rate, text=text)
