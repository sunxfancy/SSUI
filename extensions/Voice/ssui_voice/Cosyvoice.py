from ssui.model_memory import ModelMemoryOptions
from typing import Optional
import io
import random
import numpy as np
import soundfile as sf
import torch
import torchaudio
from ssui.config import SSUIConfig
from ssui.base import Audio, Voice
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider
from cosyvoice.cli.cosyvoice import CosyVoice2

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
    text_frontend: bool = True,
):
    if config.is_prepare():
        return Voice()

    seed = int(config["seed"])
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)

    # Convert prompt audio to the required format if provided
    prompt_speech_16k = None
    if prompt_audio and config["zero_shot_prompt"]:
        speech, sr = torchaudio.load(prompt_audio.path or io.BytesIO(prompt_audio._audio), backend="soundfile")
        prompt_speech_16k = torchaudio.functional.resample(speech.mean(dim=0, keepdim=True), sr, 16000)

    # Generate audio based on configuration
    if config["use_zero_shot"]:
        if prompt_speech_16k is not None:
            if not prompt_text.strip():
                raise ValueError("Zero-shot synthesis requires the reference audio transcript (prompt_text)")
            # Use zero-shot with prompt
            outputs = model.getModel().inference_zero_shot(
                text,
                prompt_text,
                prompt_speech_16k,
                stream=False,
                text_frontend=text_frontend,
            )
        else:
            speaker = f"speaker_{config['speaker_id']}"
            if speaker not in model.getModel().frontend.spk2info:
                raise ValueError("Provide reference audio and prompt_text, or register the selected speaker first")
            # Use zero-shot without prompt
            outputs = model.getModel().inference_zero_shot(
                text,
                "",
                "",
                zero_shot_spk_id=f"speaker_{config['speaker_id']}",
                stream=False,
                text_frontend=text_frontend,
            )
    else:
        if prompt_speech_16k is None:
            raise ValueError("Cross-lingual synthesis requires reference audio")
        # Use cross-lingual inference
        outputs = model.getModel().inference_cross_lingual(
            text,
            prompt_speech_16k,
            stream=False,
            text_frontend=text_frontend,
        )

    chunks = [chunk['tts_speech'].detach().cpu() for chunk in outputs]
    if not chunks:
        raise RuntimeError("CosyVoice2 produced no audio")
    output_audio = torch.cat(chunks, dim=-1)

    buffer = io.BytesIO()
    sf.write(buffer, output_audio.squeeze(0).numpy(), model.getModel().sample_rate, format="WAV")
    return Voice("wav", buffer.getvalue(), fps=model.getModel().sample_rate, text=text)
