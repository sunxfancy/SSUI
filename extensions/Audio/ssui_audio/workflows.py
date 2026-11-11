"""SSUI workflow helpers; heavyweight model dependencies load on demand."""

import os
import tempfile
from pathlib import Path

from ssui.base import Audio

from .AceStep import AceStepModel, generate_ace_step
from .MusicGen import MusicGenModel, generate_musicgen
from .song_models import generate_song
from .stable_audio_open import StableAudioOpenModel


def musicgen(prompt: str, duration_seconds: float = 10) -> Audio:
    model = MusicGenModel.load(os.environ.get("SSUI_MUSICGEN_MODEL", "facebook/musicgen-small"))
    return generate_musicgen(model, prompt, duration_seconds=duration_seconds)


def ace_step(prompt: str, lyrics: str = "") -> Audio:
    model = AceStepModel.load(os.environ["SSUI_ACE_STEP_ROOT"])
    return generate_ace_step(model, prompt, lyrics=lyrics)


def stable_audio(prompt: str) -> Audio:
    model = StableAudioOpenModel.load(os.environ.get("SSUI_STABLE_AUDIO_MODEL", "stabilityai/stable-audio-open-1.0"))
    output = Path(tempfile.mkdtemp(prefix="ssui-stable-audio-")) / "sample.wav"
    return Audio.load(model.generate(prompt, output, seconds=10))


def song(model: str, prompt: str, lyrics: str) -> Audio:
    key = model.lower()
    extension = {"yue2": ".flac", "heartmula": ".mp3", "diffrhythm": ".wav"}[key]
    output = Path(tempfile.mkdtemp(prefix="ssui-song-")) / ("song" + extension)
    source = os.environ.get(f"SSUI_{key.upper()}_SOURCE")
    dependency_dir = os.environ.get(f"SSUI_{key.upper()}_DEPS")
    if key == "diffrhythm" and source and not dependency_dir:
        for name in ("diff-compat-site", "diff-site"):
            candidate = Path(source).resolve().parent / name
            if candidate.is_dir():
                dependency_dir = str(candidate)
                break
    result = generate_song(
        key, prompt, lyrics, output,
        source_dir=source,
        checkpoint_dir=os.environ.get(f"SSUI_{key.upper()}_CHECKPOINT"),
        vae_dir=os.environ.get("SSUI_YUE2_VAE") if key == "yue2" else None,
        dependency_dir=dependency_dir,
        python_executable=os.environ.get(f"SSUI_{key.upper()}_PYTHON", os.sys.executable),
    )
    return Audio.load(result["output_path"])
