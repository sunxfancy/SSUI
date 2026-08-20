"""确定性假模型与假 API，用于 CPU 上的接口/流程测试。

设计原则：上游模型本身已由各自项目验证，SSUI 只需要确认
"给定某个模型输出，后续流程能跑通"，因此用固定 seed 的小张量、
小图、小音频替代真实推理，全部在 CPU 上运行、无需下载模型。
"""

from .audio import FakeCosyVoice
from .llm import FakeLLM, FakeTokenizer
from .sd import (
    FakeCondition,
    FakeFluxModel,
    FakeLatent,
    FakeSD1Model,
    FakeSDXLModel,
    fake_clip,
    fake_decode,
    fake_denoise,
    fake_latent,
)

__all__ = [
    "FakeCosyVoice",
    "FakeLLM",
    "FakeTokenizer",
    "FakeCondition",
    "FakeFluxModel",
    "FakeLatent",
    "FakeSD1Model",
    "FakeSDXLModel",
    "fake_clip",
    "fake_decode",
    "fake_denoise",
    "fake_latent",
]
