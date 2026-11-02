# 常见生成模型实测记录

验证日期：2026-10-27；原生依赖与 TRELLIS 续验：2026-10-28；Linux 安装集成与 CogVideoX 对照：2026-10-30。设备：RTX 3090 24 GB，主机 RAM 16 GB。
环境：Python 3.12.8、PyTorch 2.4.1+cu124、Diffusers 0.33.1、Transformers 4.46.2。
CUDA 已通过真实张量运算检查。模型文件与生成产物位于当前工作树的 `.build/`，不提交 Git。

## 已完成真实推理

| 类别 | 模型 | 参数与验收 | 产物 |
|---|---|---|---|
| 生图 | SD1.5 | 512×512；SSUI 加载、编码、采样、解码通过；人工查看图片 | `.build/model-results/sd1/result.png` |
| 生图 | Flux Schnell NF4 | T5 Int8；1024×1024、4 步；SSUI 完整推理、5 GB 主机 RAM 限额下完成；已查看图片 | `.build/model-results/flux/result_flux.png` |
| 生图 | SDXL 1.0 | 1024×1024、30 步；SSUI 完整推理通过；5 GB 主机 RAM 进程限额下完成 | `.build/model-results/sdxl/result_sdxl.png` |
| 视频 | DreamShaper 8 + AnimateDiff v2 | 256×256、16 帧、12 步；MP4 实测 H.264、8 FPS | `.build/model-results/animatediff/output.mp4` |
| 视频 | CogVideoX-2B | 官方原始 T5、720×480、49 帧、50 步；组件直接加载到 GPU，5 GB 主机 RAM 限额下 SDK/导出/解码通过；已查看明显运动 | `.build/model-results/linux-runtime/cogvideo2b/video.mp4`、`contact.png` |
| 视频 | Wan2.1 T2V-1.3B | 官方 3 权重 SHA256；256×256/12 步与 832×480/24 步均通过，17 帧；SDK 推理、MP4 及逐帧解码通过 | `.build/model-results/wan21/video.mp4`、`quality.mp4` |
| 3D | Shap-E | 64 步；24,470 顶点、48,968 三角面；GLB 导出后重新加载通过，已转换为 Y-up | `.build/model-results/shap_e/chair.glb` |
| 3D | TRELLIS image-large | SSUI 节点、12+12 步采样、1024 纹理烘焙；37,030 顶点、45,567 三角面；纹理 GLB 重读通过 | `.build/model-results/trellis/sample.glb`、`preview.png` |
| 动作 | MDM HumanML 50 steps | 2 秒、20 FPS、40 帧、22 关节；轨迹非静止；NPZ 无 pickle 重读和视频解码通过 | `.build/model-results/mdm-*/motion.npz`、`samples_00_to_00.mp4` |

下表为合并前依赖环境的留存实测；dev 0.3.0 的 Diffusers/Transformers 版本已经变化，未把旧结果作为新依赖的全量 GPU 验收。

这是各类别代表模型的真实端到端验证，不代表所有已声明的模型都已通过，也不代表质量与最新旗舰模型相当。
MDM 输出的是骨骼关节轨迹，尚不包含 FBX/BVH 转换、角色绑定和重定向。

## 重跑

先按照根 `CLAUDE.md` 和 `package.json` 安装项目基础环境。
动作模型另外按 [Motion 扩展说明](../extensions/Motion/README.md) 安装兼容依赖和官方资产。

```bash
export TEST_DATA_DIR="$PWD/.build/model-data"
export SSUI_MODEL_OUTPUT_DIR="$PWD/.build/model-results"
export HF_HOME="$PWD/.build/cache/huggingface"
export XDG_CACHE_HOME="$PWD/.build/cache"
mkdir -p .build/tmp
export TMPDIR="$PWD/.build/tmp"

SSUI_RUN_MODEL_TESTS=1 yarn test_on model.sd_model_test.TestSD1Model
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.sd_model_test.TestSDXLModel
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.sd_model_test.TestFluxModel
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.diffsynth_model_test
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.shap_e_model_test

export SSUI_MDM_REPO="$PWD/.build/model-sources/mdm"
export SSUI_MDM_CHECKPOINT=save/humanml_enc_512_50steps/model000750000.pt
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.mdm_model_test

yarn test
```

提供工作流：`examples/advance/workflow-text-to-3d.py` 和
`examples/advance/workflow-motion.py`。现有 SD1 工作流仍可使用。
上述模型回归覆盖 SDK 节点到文件输出；Linux 桌面安装与交互另见 [Linux 安装与验收](Linux.md)。

合并前默认 `yarn test`：共 81 项，79 项通过、2 项跳过；包含真实 MP4 编解码、GLB 重读、动作 NPZ 保留和 IPv4/IPv6 执行器地址和推理期间通信响应回归。

## 本次修复

- 真实模型测试在独立进程运行，指定测试不再先导入整个测试目录，避免被假模型污染。
- Wan 的帧数与采样步数分别传递；TRELLIS 接收真正的 PIL 图像。
- 旧版 Transformers 不再因未使用的 Qwen 图像编码器顶层导入而无法加载视频模型。
- DreamShaper 的 404 地址改为官方单文件权重并固定 revision。
- SD1、SDXL、DreamShaper、AnimateDiff 已补 SHA256；下载验证长度、以临时文件原子发布，已存在文件也检查配置的哈希。
- LLM、CosyVoice、TRELLIS 回归使用下载后的本地目录；TRELLIS 改用已有有效图片输入。
- 增加 Shap-E 文生网格与 MDM 文本动作适配器；可通过环境变量保留真实回归产物。

## 尚未完成的覆盖

- 原有 CogVideoX-5B、HunyuanVideo 等其他模型：尚未真实推理验收。
- LTX-2.5：已用固定 revision `49b093a39c19169a8a81721dcc541e07e945232f` 实际检查权重访问，当前凭据返回 `GatedRepoError / HTTP 401`，需要账号获得官方门控仓库权限，未进行推理。
- StdGEN：清单本身仍要求手动放置模型；未真实验收。
- LLM、CosyVoice：本次仅修正本地权重路径，未真实推理验收。

完整 `SSUI_RUN_MODEL_TESTS=1 yarn test` 会包括这些未验收模型，需要全部权重、依赖和 MDM 资产；当前不宣称该完整门禁通过。

参考：[Shap-E 官方 Diffusers 文档](https://huggingface.co/docs/diffusers/api/pipelines/shap_e)、
[MDM 官方实现](https://github.com/GuyTevet/motion-diffusion-model)、
[TRELLIS 官方安装说明](https://github.com/microsoft/TRELLIS/blob/main/setup.sh)。

## CUDA 原生扩展（已真实验证）

工具链放在 `.build/cuda-env`：CUDA nvcc 12.4.131、GCC/G++ 12.4、glibc 2.17 sysroot。
正常安装使用 `yarn install:native` / `yarn doctor:native`，详见 [Linux 安装与验收](Linux.md)。
以下保留最初手工验证的复现方式；环境清单是 `dependencies/native-cuda-linux.yaml`，通过工作树内 micromamba 2.10.0 创建。
可选 Python 原生依赖集中在 `dependencies/requirements-native-cuda-linux.txt`，针对 Linux x86_64 / Python 3.12 / Torch 2.4.1+cu124。
`nvdiffrast==0.3.3` 已通过 CUDA 栅格化、插值、抗锯齿和反向梯度回归。
TRELLIS 导出实际调用 Gaussian 栅格化和 nvdiffrast，已完成纹理 GLB。

```bash
# 先准备 micromamba；其官方入口 https://micro.mamba.pm/api/micromamba/linux-64/latest
export MAMBA_ROOT_PREFIX="$PWD/.build/mamba"
export TMPDIR="$PWD/.build/tmp"
.build/tool-bootstrap/bin/micromamba create -y -p "$PWD/.build/cuda-env" -f dependencies/native-cuda-linux.yaml
scripts/model_native_env.sh node dependencies/venv.cjs python -m pip install --no-build-isolation \
  -r dependencies/requirements-native-cuda-linux.txt
SSUI_RUN_MODEL_TESTS=1 scripts/model_native_env.sh yarn test_on model.nvdiffrast_model_test

export SSUI_DINOV2_REPO="$PWD/.build/model-sources/dinov2"
export SSUI_DINOV2_WEIGHTS="$PWD/.build/cache/torch/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth"
SSUI_RUN_MODEL_TESTS=1 scripts/model_native_env.sh yarn test_on model.trellis_model_test
```

DINOv2 源码版本 `7764ea0f912e53c92e82eb78a2a1631e92725fc8`。
TRELLIS 固定微软官方模型 revision `25e0d31ffbebe4b5a97464dd851910efc3002d96`。
提供本地 DINOv2 路径可避免 Torch Hub 的 GitHub API 限流；映射权重和空参数初始化
将加载峰值控制在本次验证的 5 GB 进程内存限制内。

启动需要 TRELLIS 原生扩展的服务时也使用同一环境入口：

```bash
scripts/model_native_env.sh yarn dev:server:no_build
scripts/model_native_env.sh yarn dev:executor
```

这样服务运行时能找到匹配的 nvcc/GCC 和已编译的 Torch 扩展缓存。
本轮额外安装的量化库是 bitsandbytes 0.45.5，NF4 和 Int8 CUDA 内核均已实测。

Wan 1.3B 本地工作流为 `examples/advance/workflow-wan21.py`；新版 Wan DiT 的原始 patch 网格已在旧管线中正确展平，并用单批/多批小模型进行直接 forward 数值对照。

Flux 四组件固定官方仓库 revision 和 SHA256，T5 损坏缓存已经隔离并从固定版本完整重建，整文件校验通过后才进行推理。下载器不会把主权重摘要错误应用到辅助配置文件。

## CogVideoX-2B 本地入口与动态对照

`examples/advance/workflow-cogvideo2b.py` 使用 `CogVideo2BModel.load(model_path)`。
清单 `cogvideo2b` 包含官方原始 T5；默认 49 帧、50 步，组件直接加载到 GPU，
避免 9.5 GB 文本编码器在 CPU 中驻留导致 5 GB 限额下 OOM。

同种子、同提示词、同采样参数的对照结果：旧 Int8 T5 路径全帧时间标准差均值约 1.53，
官方原始 T5 约 5.08，后者的小车从左向右驶出画面。新的正式 SDK 回归片段约 8.01，
已查看首、中、尾帧，小车有明显位置和朝向变化。这个指标仅用于定位，不能单独充当质量评分。
原始 T5 对照产物在 `.build/model-results/cogvideo2b/original-t5/`。

可选 `quantized_t5_path` 仍支持 `flux.t5_encoder` 的 Int8 权重以节省显存，
但本次对照中该量化权重显著削弱运动，因此不再作为默认验收路径。
此入口与原有 CogVideoX-5B/DiffSynth 节点分别保留。

```bash
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.cogvideo_model_test
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.wan_model_test
```

参考：[CogVideoX-2B 官方模型](https://huggingface.co/zai-org/CogVideoX-2b)、
[Diffusers 0.33.1 CogVideoX 文档](https://huggingface.co/docs/diffusers/v0.33.1/en/api/pipelines/cogvideox)。
