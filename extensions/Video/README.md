# Video 扩展：本地视频生成模型接入说明

本扩展内置了 vendored [diffsynth 1.1.9](https://pypi.org/project/diffsynth/)（`extensions/Video/diffsynth`），
在引擎能力范围内支持 Wan 2.2（含 TI2V-5B / T2V-A14B / I2V-A14B）、Wan 2.1、HunyuanVideo、CogVideoX 等模型。

> diffsynth 目前最高只支持到 **Wan 2.2**；Wan 2.5/2.6/2.7 尚未被 diffsynth 集成，
> 需要走官方 Wan 仓库或 diffusers（不在本扩展范围内）。

## 依赖

Windows 安装环境需要补充 `modelscope==1.26.0`（Wan 系列节点下载权重时使用）。
已加入 `dependencies/requirements-windows.txt` 与 `requirements-windows-amdgpu.txt`；
改依赖后请在有 venv 的机器上重新生成锁文件：

```bash
yarn update-lock:no-upgrade
```

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
FP8：把 `Wan22.py` 里三个 `load()` 的 `torch_dtype=torch.bfloat16` 改为 `torch.float8_e4m3fn`。

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

- diffsynth 由仓库原 vendored 版本整体替换为 PyPI `diffsynth==1.1.9` 源码（无本地补丁，git 可回滚）。
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
