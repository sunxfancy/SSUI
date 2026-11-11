# CosyVoice2

Voice 使用仓库内的 `vendor/cosyvoice` 与 `vendor/matcha`，Python 依赖统一由根目录
`dependencies/dependencies.yaml` 声明，并生成各平台 requirements、lock 和依赖图。
无需进入 Voice 目录另建 venv，也不要安装上游训练 requirements 覆盖 SSUI 的 Torch。

macOS 上 Pynini 2.1.7 没有 PyPI wheel，需要 OpenFst 1.8.4 的 GRM 头文件和动态库。
根目录安装器与 Mac CI 会通过 Homebrew 安装并检查该前置库，并传入编译器/链接器路径；
因此 Mac 开发环境需要先安装 Homebrew。锁文件解析与安装均沿用
`dependencies/build-constraints.txt` 的隔离构建约束，避免 Whisper 构建时丢失 `pkg_resources`。
Intel CI 使用验证后的原生 PyTorch wheel 解析完整锁，并将该锁交给后续完整安装与运行检查。

## 从根目录运行

先按 SSUI 的标准流程安装对应运行时。Windows AMD 使用项目的 Windows x64 ROCm
配置和 ROCm PyTorch；`torch.cuda.is_available()` 在 ROCm 下也应为 `True`。
已有环境新增依赖后使用 `yarn install-requirements`，环境路径选择见
[`doc/DevelopmentEnvironments.md`](../../doc/DevelopmentEnvironments.md)。

```powershell
# 下载固定版本官方权重、参考音频，生成中文语音并检查 GPU 驻留和输出。
yarn probe:cosyvoice --download --require-rocm

# 使用本地模型与自己的参考音频；prompt-text 必须是参考音频的真实转写。
yarn probe:cosyvoice --require-rocm --model-dir 'D:/models/CosyVoice2-0.5B' --prompt 'D:/voice/reference.wav' --prompt-text '参考音频中说的原文。'

# 同一参考音色生成英文，不要求参考音频转写。
yarn probe:cosyvoice --download --require-rocm --cross-lingual --text 'Hello, welcome to speech synthesis.'
```

默认模型目录为根目录 `.build/models/CosyVoice2-0.5B`，输出为 `.build/cosyvoice/` 下的
`zero_shot.wav` 或 `cross_lingual.wav`，旁边的 JSON 保存设备、采样率、时长、耗时及幅度。
`--output-dir` 可更改输出目录。模型 revision 固定为
`eec1ae6c79877dbd9379285cf8789c9e0879293d`，下载仅包含推理必需文件，约 4.1 GB。
官方参考音频通过 SHA-256 校验。首次启动需要构建中英文文本规范化 FST 缓存。

探针默认使用 4 个 CPU 线程，支持 `--threads` 调整；缓存写入 `.build/`。
应用内的文本规范化缓存默认位于 `HF_HOME/ssui/cosyvoice2-tn-v1`（无 HF_HOME 时使用
`~/.cache/ssui/cosyvoice2-tn-v1`），可通过 `SSUI_COSYVOICE_TN_CACHE` 覆盖。

## SSUI 接口

```python
from ssui.base import Audio
from ssui_voice.Cosyvoice import CosyVoiceModel, GenVoice

model = CosyVoiceModel.load("D:/models/CosyVoice2-0.5B")
voice = GenVoice(
    config("Text to Speech"), model, "你好，欢迎使用语音合成。",
    Audio.load("D:/voice/reference.wav"),
    prompt_text="参考音频中说的原文。",
)
```

`use_zero_shot=True` 时必须同时提供参考音频和 `prompt_text`，或先通过
`model.getModel().add_zero_shot_spk(...)` 注册 `speaker_0` 等 speaker ID。
`use_zero_shot=False` 走跨语言模式，仍需要参考音频。
`zero_shot_prompt=False` 表示不读取传入音频，适用于已注册 speaker 的零样本模式。
生成器会拼接所有句子的音频，返回 24 kHz `Voice`。

## ROCm 路径与验证

2026-11-07 在 Windows、AMD Radeon AI PRO R9700、PyTorch `2.9.1+rocm7.2.1`
上完成真实权重验证：LLM、Flow、HiFT 均为 `cuda:0`（PyTorch 的 HIP 设备命名），
使用 FP32；ONNX 声纹与语音分词前处理使用 CPUExecutionProvider。
无需 NVIDIA CUDA、TensorRT、vLLM 或 FlashAttention。
SoundFile 负责文件解码，避免 torchaudio 2.9 的 TorchCodec 依赖。

中文输入“你好，这是使用 AMD 显卡生成的语音。欢迎使用语音合成。”生成约 6.68 秒音频；
中文参考音色生成英文“Hello, welcome to speech synthesis.”约 2.12 秒。
两份输出均通过有限值、非静音检查，并用 Whisper base 独立识别确认对应内容。
这些是本机功能验证，不代表其他 GPU 或平台已完成推理验收，也不代表实时速度。

```powershell
yarn test_on cosyvoice_adapter_test
yarn test_on cosyvoice_cache_test
$env:SSUI_RUN_MODEL_TESTS = '1'
$env:SSUI_COSYVOICE_REQUIRE_ROCM = '1'
yarn test_on model.cosyvoice_model_test
```

真实模型测试默认下载到配置的 `TEST_DATA_DIR/cosyvoice`，可设置
`SSUI_COSYVOICE_MODEL_DIR` 使用已有权重，`SSUI_COSYVOICE_PROMPT` 复用官方参考音频。
自定义参考转写请直接使用探针的 `--prompt-text`。

Intel macOS 锁文件已使用经过源码版本、架构和哈希验证的原生 PyTorch wheelhouse 完整解析。
后续刷新时，先取得项目要求的已验证 wheelhouse，设置 `SSUI_NATIVE_WHEELHOUSE`，再运行
`yarn update-lock:no-upgrade --target macosx-x86_64`。

上游：[CosyVoice](https://github.com/FunAudioLLM/CosyVoice)、
[CosyVoice2 权重](https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B)。
