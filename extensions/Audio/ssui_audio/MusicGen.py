"""MusicGen text-to-music adapter (optional Transformers dependency)."""

from __future__ import annotations

import tempfile
import os
import uuid
from pathlib import Path

from ssui.base import Audio


class MusicGenModel:
    def __init__(self, model, processor, model_path: str):
        self.model = model
        self.processor = processor
        self.model_path = model_path

    @staticmethod
    def load(model_path: str = "facebook/musicgen-small") -> "MusicGenModel":
        try:
            import torch
            from transformers import MusicgenForConditionalGeneration, MusicgenProcessor
        except ImportError as exc:
            raise RuntimeError("MusicGen requires transformers; install it in the Audio extension environment") from exc

        processor = MusicgenProcessor.from_pretrained(model_path)
        model = MusicgenForConditionalGeneration.from_pretrained(model_path)
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        model.to(device).eval()
        return MusicGenModel(model, processor, model_path)


def generate_musicgen(
    model: MusicGenModel,
    prompt: str,
    duration_seconds: float = 10.0,
    seed: int = 42,
) -> Audio:
    import torch

    if not prompt.strip():
        raise ValueError("MusicGen prompt must not be empty")
    if not 1 <= duration_seconds <= 30:
        raise ValueError("MusicGen duration_seconds must be between 1 and 30")

    inputs = model.processor(text=[prompt], padding=True, return_tensors="pt")
    device = next(model.model.parameters()).device
    inputs = {name: value.to(device) for name, value in inputs.items()}
    # MusicGen predicts 50 audio tokens per second. Keep the model's 30 s limit.
    fork_devices = [device.index or 0] if device.type == "cuda" else []
    with torch.random.fork_rng(devices=fork_devices), torch.inference_mode():
        torch.manual_seed(int(seed))
        waveform = model.model.generate(**inputs, max_new_tokens=int(duration_seconds * 50), do_sample=True)
    # SSUI's executor can copy a WAV path without requiring TorchCodec, which
    # torchaudio.save needs with current PyTorch builds on Windows ROCm.
    import soundfile as sf

    sample_rate = model.model.config.audio_encoder.sampling_rate
    output_dir = Path(os.environ.get("SSUI_AUDIO_TEMP_DIR", tempfile.gettempdir()))
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"ssui-musicgen-{uuid.uuid4().hex}.wav"
    sf.write(output, waveform[0].detach().float().cpu().T.numpy(), sample_rate)
    return Audio(format="wav", path=str(output), sample_rate=sample_rate)
