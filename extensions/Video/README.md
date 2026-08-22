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
80GB 单卡用 bf16 + 自动 offload；24-32GB 建议节点参数选 `int8` 量化（需安装 torchao）。
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

环境变量：

```text
SSUI_H3_PYTHON   H3 venv 的 python（默认探测 h3-venv 与系统 python）
SSUI_H3_MODEL_ID 模型仓库 id（默认 MiniMaxAI/MiniMax-H3）
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
