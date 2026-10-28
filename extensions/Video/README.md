# Video 扩展：本地视频生成模型接入说明

本扩展内置了 vendored [diffsynth 1.1.9](https://pypi.org/project/diffsynth/)（`extensions/Video/diffsynth`），
在引擎能力范围内支持 Wan 2.2（含 TI2V-5B / T2V-A14B / I2V-A14B）、Wan 2.1、HunyuanVideo、CogVideoX 等模型。

> diffsynth 目前最高只支持到 **Wan 2.2**；Wan 2.5/2.6/2.7 尚未被 diffsynth 集成，
> 需要走官方 Wan 仓库或 diffusers（不在本扩展范围内）。

## 依赖

macOS 的基础依赖和锁文件已包含 ModelScope、imageio/FFmpeg、SentencePiece、ftfy、pandas。
在根目录运行 `yarn install-requirements` 安装到 `.venv`。
AnimateDiff、CogVideoX、Wan 2.1 和 Wan 2.2 节点已接入设备选择；Wan 在现代 MPS 默认 BF16，
CPU 或旧版 macOS 使用 float32。AnimateDiff 已通过真实权重的 MPS 完整视频生成（最高实测 512×512、8 帧）；
Wan 1.3B 已通过下述分阶段完整短视频生成；CogVideo、Wan Fun/14B 和 Wan 2.2 目前仍只通过算子/小型模型测试。
Wan 2.2、Hunyuan、H3 等的支持边界见 [Mac 模型支持检查](../../doc/MacModelSupport.md)。

Windows 安装环境需要补充 `modelscope==1.26.0`（Wan 系列节点下载权重时使用）。
已加入 `dependencies/requirements-windows.txt` 与 `requirements-windows-amdgpu.txt`；
改依赖后请在有 venv 的机器上重新生成锁文件：

```bash
yarn update-lock:no-upgrade
```

## Mac 完整 AnimateDiff 流程

当前工作树已有独立 `.venv` 时，在根目录执行：

```bash
# 首次下载约 3.7GB，固定版本并校验 SHA-256；后续复用本地文件。
yarn test:video:smoke --download-only
# 实际经过 SSUI 沙盒工作流、真实模型推理、MP4 编码与解码校验。
yarn test:video:smoke --local-files-only --workflow --device mps --size 256 --frames 8 --steps 20
```

产物在 `output/video-smoke/`：`animatediff.mp4`、`preview.png`、`report.json`。
`--output` 可指定其他输出目录。无 MPS 的机器可用 `--device cpu`，但运行会慢很多。
普通测试不会自动下载这些权重。真模型回归单独运行：

```bash
SSUI_RUN_MODEL_TESTS=1 SSUI_VIDEO_MODEL_DIR="$PWD/models/video-smoke" yarn test_on model.diffsynth_model_test
```

桌面端可打开 `examples/advance/workflow-video-mac.py`，使用 `txt2vid_animatediff`。
默认 256×256、8 帧、20 步；按内存和耗时再提高尺寸。模型默认读取本仓库
`models/video-smoke/`，也可用 `SSUI_ANIMATEDIFF_CHECKPOINT` 和
`SSUI_ANIMATEDIFF_MOTION` 指向其他本地文件。准备/读取节点参数时不加载模型。
两阶段生成均使用指定 seed；MPS 的随机噪声在 CPU 上生成后传入 GPU。

## Mac 低内存 Wan 1.3B 流程

根目录新增 `yarn test:wan:smoke`，使用固定版本的官方 `Wan-AI/Wan2.1-T2V-1.3B`。
首次下载约 17.6GB，校验三个权重的 SHA-256。三个独立进程依次执行：
UMT5 文件映射和逐层 MPS 编码、BF16 DiT 去噪、float32 VAE 解码。
每阶段退出后释放模型，避免文本编码器、DiT、VAE 同时驻留统一内存。

```bash
yarn test:wan:smoke --download-only
yarn test:wan:smoke --local-files-only --size 256 --frames 9 --steps 30
```

输出目录为 `output/wan-mac/`，包含 `wan.mp4`、`preview.png`、`report.json`，
以及用于排错的提示词编码和 latent。帧数必须为 `4n+1`，尺寸必须为 16 的倍数。
报告记录阶段耗时、进程 RSS、系统可用内存和交换空间；系统指标也包含其他应用的影响。
已在本机 16GB Mac / Torch 2.4.1 实测 256×256、9 帧、30 步成功，约 97 秒，
生成约 1.1 秒的橘猫行走视频。后续帧有模糊和重影，仅证明低内存完整链路可用。
128×128 / 8 步虽能编码 MP4，但仅形成色块，不能作为质量通过的样例。
已验证产物保存在 `output/wan-mac-preview/`。

此脚本为独立低内存入口，已有 Wan 14B / Fun 节点不会自动使用它。

## 节点一览

### Wan 2.2（进程内推理，权重经 ModelScope 自动下载）

`ssui_video/Wan22.py`：

| 节点 | 模型 | 说明 | 显存建议 |
|------|------|------|----------|
| `Wan22TextToVideo` | Wan-AI/Wan2.2-TI2V-5B | 文生视频 | 24GB+ |
| `Wan22ImageToVideo` | Wan-AI/Wan2.2-TI2V-5B | 图生 / 首尾帧视频 | 24GB+ |
| `Wan22T2VA14BTextToVideo` | Wan-AI/Wan2.2-T2V-A14B | MoE 双专家文生 | 48GB+（24GB 建议改 FP8） |
| `Wan22I2VA14BImageToVideo` | Wan-AI/Wan2.2-I2V-A14B | MoE 双专家图生 | 48GB+（24GB 建议改 FP8） |

权重下载到 `models/`（可用环境变量 `SSUI_WAN_MODEL_ROOT` 覆盖），
文本编码器 / tokenizer / VAE 与 Wan2.1 共享，会自动重定向下载。
Mac 不支持这里的 CUDA FP8 路径。CPU 卸载仍占统一内存，不能据此保证 16GB Mac 可以加载完整 Wan 权重。

### LTX-2.5（独立 venv + subprocess）

`ssui_video/LTX2.py`：

| 节点 | 管线 | 权重 |
|------|------|------|
| `LTX2TextToVideo` | `ltx_pipelines.distilled`（8 步蒸馏，最快） | `ltx-2.5-22b-distilled-transformer-bf16.safetensors` |
| `LTX2ImageToVideo` | `ltx_pipelines.ti2vid_one_stage`（单阶段，40 步） | `ltx-2.5-22b-dev-transformer-bf16.safetensors` |

LTX-2.5 官方栈要求 **Python>=3.12 / PyTorch~=2.7 / CUDA>=12.7**，与 SSUI 主环境（torch 2.4.1）冲突，
所以必须建独立 venv（建议放仓库根目录的 `ltx-venv/`）：

```bash
git clone https://github.com/Lightricks/LTX-2.git && cd LTX-2
uv sync --extra natten        # Windows/macOS 自动跳过 natten，走 Triton/eager 后端
# 或: pip install -e "packages/ltx-pipelines[all]"
```

权重（HF 门控仓库 `Lightricks/LTX-2.5`，约 66 GiB，需先同意许可并登录）：

```bash
hf auth login
hf download Lightricks/LTX-2.5 \
    diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors \
    diffusion_models/ltx-2.5-22b-dev-transformer-bf16.safetensors \
    text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
    vae/ltx-2.5-video-vae-bf16.safetensors \
    vae/ltx-2.5-audio-vae-bf16.safetensors \
    latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
    --local-dir models/ltx-2.5
```

节点默认按上述目录布局找权重；如不满足，用环境变量覆盖：

```text
SSUI_LTX_PYTHON      LTX venv 的 python（默认探测 ltx-venv 与系统 python）
SSUI_LTX_MODEL_ROOT  权重根目录（默认 models/ltx-2.5）
SSUI_LTX_TRANSFORMER / SSUI_LTX_TRANSFORMER_DEV / SSUI_LTX_TEXT_ENCODER /
SSUI_LTX_VIDEO_VAE / SSUI_LTX_AUDIO_VAE / SSUI_LTX_SPATIAL_UPSAMPLER  单个权重路径
```

### MiniMax H3（独立 venv + subprocess）

`ssui_video/MiniMaxH3.py` + `ssui_video/h3_runner.py`：

| 节点 | 任务 | 说明 |
|------|------|------|
| `H3TextToVideo` | t2va | 文生视频 + 原生音频，768p |
| `H3ImageToVideo` | fl2va | 首帧 / 首尾帧视频 + 原生音频，768p |

H3 是 33B 全模态 DiT，效果最接近 Seedance 2.0 的开源模型，但本地推理很吃硬件：
80GB 单卡可用 bf16 + 自动 offload；24-32GB 可选 `int8`（需 torchao）。
消费级显卡还可显式选择 `nf4`，使用 DiffSynth-Studio 的 pruned NF4 权重与磁盘卸载；
官方标称最低 7GB 显存，但仍需约 26GiB 本地权重空间和足够的系统内存/磁盘交换空间。
H3-Context-IR 与 2K 重生成模块官方未开源，本地只能到 768p；
想复现官方效果需按 [Prompting Guidance](https://github.com/MiniMax-AI/MiniMax-H3) 自行预处理提示词。

独立 venv（建议 `h3-venv/`，Python>=3.12）：

```bash
hf auth login   # 先同意 MiniMaxAI/MiniMax-H3 的许可
python -m venv h3-venv
h3-venv/Scripts/pip install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
h3-venv/Scripts/pip install -U "diffusers" "transformers" "torchao" "pyav" "Pillow" "sentencepiece" "accelerate"
```

> diffusers 的 `ModularPipeline` / MiniMax-H3 支持是较新特性，请安装最新版。

NF4 使用当前 DiffSynth-Studio，而不是扩展中兼容旧节点的 vendored 1.1.9。可在同一
H3 venv 中安装 GitHub main，或用 `SSUI_H3_DIFFSYNTH_ROOT` 指向源码 checkout；并安装
`bitsandbytes`（Windows AMDGPU 使用仓库 AMD requirements 中的 ROCm wheel）。下载
`DiffSynth-Studio/MiniMax-H3-NF4` 的以下四个文件到 `models/minimax-h3-nf4/`：

```text
minimax-h3-fl2va-pruned-nf4.safetensors
minimax-h3-text-encoder-nf4.safetensors
video_vae_nf4.safetensors
audio_vae_nf4.safetensors
```

环境变量：

```text
SSUI_H3_PYTHON   H3 venv 的 python（默认探测 h3-venv 与系统 python）
SSUI_H3_MODEL_ID 模型仓库 id（默认 MiniMaxAI/MiniMax-H3）
SSUI_H3_NF4_MODEL_ROOT NF4 四个权重文件的目录（默认 models/minimax-h3-nf4）
SSUI_H3_DIFFSYNTH_ROOT 当前 DiffSynth-Studio 源码目录（已安装到 venv 时可省略）
SSUI_H3_PROCESSOR_MODEL_ID processor 仓库（默认 MiniMax/MiniMax-H3）
SSUI_H3_VRAM_RESERVE_GIB 为激活和桌面预留的显存 GiB（默认 2）
```

## 工作流示例

`examples/advance/workflow-video-local.py` 已包含全部节点的示例 workflow：

```text
txt2vid_wan22 / img2vid_wan22 / txt2vid_wan22_a14b / img2vid_wan22_a14b
txt2vid_ltx25 / img2vid_ltx25
txt2vid_h3 / img2vid_h3
```

## 引擎升级说明

- diffsynth 由仓库原 vendored 版本整体替换为 PyPI `diffsynth==1.1.9` 源码（含本仓库的 Mac 兼容性补丁，git 可回滚）。
- 1.1.9 新增 `pipelines/wan_video_new.py`（Wan 2.2 系列入口，`WanVideoPipeline.from_pretrained`）与
  `models/wan_video_dit_s2v.py`、`wan_video_mot.py`、`wan_video_animate_adapter.py` 等。
- 顶层 `diffsynth.WanVideoPipeline` 仍是旧版（Wan 2.1），Wan 2.2 节点显式导入
  `diffsynth.pipelines.wan_video_new.WanVideoPipeline` 与 `diffsynth.utils.ModelConfig`。
- 旧节点（Wan2 / Hunyuan / CogVideo）使用的 `from_model_manager`、`download_models` 等 API 在 1.1.9 中原样保留。

## Qwen-Image 节点

本扩展同时拥有仓库 vendored DiffSynth 运行时，因此
`ssui_video.QwenImage` 在这里提供 Qwen-Image 生成和参考图编辑节点，
避免在 Image 扩展中重复打包同一套推理实现。

默认生成模型为 `Qwen/Qwen-Image`，参考编辑默认使用当前 vendored
DiffSynth 支持的多参考图模型 `Qwen/Qwen-Image-Edit-2509`。只有调用
`QwenImageModel.load()` 或 `QwenImageEditModel.load()` 时才会下载权重。

像素游戏资产可直接使用一体化节点 `QwenPixelArtGenerate` 与
`QwenPixelArtEdit`。两者默认采用已经在 32 GiB AMD GPU 上实测通过的
512×512、20 步、CFG 1.0 生成参数，并直接输出 64×64、24 色的像素网格
（默认以 4 倍 nearest-neighbor 尺寸预览）。通用节点 `QwenImageGenerate`
与 `QwenImageEdit` 仍保留，用于非像素工作流或自定义后处理。

可用环境变量：

```text
SSUI_QWEN_IMAGE_MODEL_ROOT       权重目录（默认 models）
SSUI_QWEN_IMAGE_DOWNLOAD_SOURCE  ModelScope（默认）或 HuggingFace
SSUI_QWEN_IMAGE_VRAM_LIMIT_GIB   低显存模式的模型常驻显存上限（GiB）
```

`low_vram=True` 会让各组件在阶段之间驻留 CPU，降低显存占用，但仍需要
较大的系统内存和磁盘空间；当前 SSUI Qwen-Image 节点要求 CUDA。32 GiB
显存运行 512×512 时，可在模型加载参数中设置 `vram_limit_gib=24`，为激活
和 VAE 解码预留空间。设为 `0` 时沿用自动值或上述环境变量。

## Windows AMD / ROCm validation

On Radeon AI PRO R9700 (gfx1201), Windows Python 3.12 and Torch
2.9.1+rocm7.2.1, the real AnimateDiff SSUI sandbox workflow generated and
round-trip decoded a 512x512, 16-frame MP4 (seed 42, 20 steps). Model loading
plus generation took 40.5 seconds after initial kernel warmup, with 3.92 GiB
peak allocated VRAM and 2.69 GiB peak process working set. The orange-cat
sequence shows changing legs/tail across the clip; this is a short smoke test,
not a long-video quality guarantee. A 256x256 lake example was nearly static
and missed the requested sailboat, so successful encoding alone is insufficient.

```powershell
yarn test:video:smoke --device cuda --size 512 --frames 16 --steps 20 --workflow --prompt "A small orange cat walking slowly across a green lawn, daylight, fixed camera, realistic video."
```

`cuda` is also PyTorch's device name on ROCm. Reports include HIP version,
GPU name, peak allocated VRAM and (on Windows) peak process working set.
The preview samples the entire clip instead of only its first frames.
Wan 2.1 T2V-1.3B also passed full staged generation on this host: 512x512,
17 frames at 8 FPS, seed 42, 30 steps and CFG 5. All three pinned checkpoints
passed SHA256 verification. Text encoding took 14.6 seconds, denoising 26.9
seconds and FP32 VAE decoding 178.8 seconds (237.4 seconds including checkpoint
verification and subprocess startup). Peak allocated VRAM was 14.86 GiB during
decode; peak process working set was 9.90 GiB during text encoding. The system
retained at least 5.75 GiB available RAM. MP4 round-trip checks passed, and sampled
frames show a coherent orange cat taking steps. The 256x256 trial had visible
ghosting; this short 512px sample does not certify long-video quality or larger
Wan variants. These measurements describe the staged model runner.

```powershell
yarn test:wan:smoke --device cuda --size 512 --frames 17 --steps 30
```

Windows ROCm 7.2's hipBLASLt crashed natively while selecting a BF16 matrix
multiplication algorithm in Wan denoising. Wan node loaders and the staged smoke
entry now select regular hipBLAS through PyTorch's `preferred_blas_library` API.
This preference is process-wide and limited to Windows ROCm 7.2 GPU runs; it is
not applied on CPU, MPS, NVIDIA CUDA or other ROCm versions. The installed Torch
build warns that this API is experimental/unsupported on Windows, but the full
generation above validates its effect on this host. Revalidate on SDK upgrades.

The download entry checks disk space before fetching missing weights. The CPU
BF16 LayerNorm offload regression, opt-in real-dependency runtime suite and eight
device-policy tests pass; these small tests are separate from the real-model run.

### Wan 1.3B SSUI workflow

Open `examples/advance/workflow-video-wan21.py` and select `txt2vid_wan21_13b`.
Download the pinned weights once with `yarn test:wan:smoke --download-only`.
The local loader uses `models/wan-mac` by default; set `SSUI_WAN21_MODEL_DIR`
to use a different directory. Preparing the workflow does not load/download
weights. The default controls are 512x512, 17 frames, 30 steps and CFG 5.
UMT5/VAE checkpoints are memory-mapped on CPU before pipeline offloading.

```powershell
yarn test:wan:smoke --device cuda --local-files-only --workflow --size 512 --frames 17 --steps 30
```

This command exercises the real sandbox, model loader, generation node and
executor video exporter, then decodes both exported MP4 files to check frame
counts/dimensions. The executor accepts both SSUI `Image` wrappers (returned by
Wan) and PIL frames. `executor_result.json` records the actual executor output.
The workflow smoke uses untiled decoding; the interactive node defaults to tiled.

On the same R9700 host, the full workflow passed with 179.1 seconds wall time,
7.51 GiB peak allocated VRAM and 16.73 GiB peak process working set. It uses BF16
VAE decoding, unlike the staged FP32 decode above. Sampled frames show coherent
cat motion. System available RAM reached 1.93 GiB, so this single-process path
is not certified for a 16 GiB RAM machine. The staged runner remains the lower
RAM option. Browser rendering and other Wan model variants remain unverified.
