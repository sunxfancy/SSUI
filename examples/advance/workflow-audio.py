"""Local music, sound effect, and song generation examples.

Install each model's optional dependencies and weights as described in
extensions/Audio/README.md before running its workflow.
"""

from ssui import Audio, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_audio.workflows import ace_step, musicgen, song, stable_audio

config = SSUIConfig()


@workflow
def musicgen_instrumental(prompt: Prompt, duration_seconds: float = 10) -> Audio:
    if config.is_prepare():
        return Audio()
    return musicgen(str(prompt), duration_seconds)


@workflow
def ace_step_instrumental(prompt: Prompt) -> Audio:
    if config.is_prepare():
        return Audio()
    return ace_step(str(prompt))


@workflow
def ace_step_song(prompt: Prompt, lyrics: str) -> Audio:
    if config.is_prepare():
        return Audio()
    return ace_step(str(prompt), lyrics)


@workflow
def stable_audio_sample(prompt: Prompt) -> Audio:
    if config.is_prepare():
        return Audio()
    return stable_audio(str(prompt))


@workflow
def full_song(prompt: Prompt, lyrics: str, model: str) -> Audio:
    """Choose yue2, heartmula, or diffrhythm; see model specific setup."""
    if config.is_prepare():
        return Audio()
    return song(model, str(prompt), lyrics)
