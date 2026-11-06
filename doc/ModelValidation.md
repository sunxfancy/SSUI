# 常见生成模型实测记录

验证日期：2026-10-27；原生依赖与 TRELLIS 续验：2026-10-28；Linux 安装集成与 CogVideoX 对照：2026-10-30。设备：RTX 3090 24 GB，主机 RAM 16 GB。
环境：Python 3.12.8、PyTorch 2.4.1+cu124、Diffusers 0.33.1、Transformers 4.46.2。
CUDA 已通过真实张量运算检查。模型文件与生成产物位于当前工作树的 `.build/`，不提交 Git。

## 2026-11-06 当前 dev 依赖复验

环境为 Python 3.12.8、Torch 2.4.1+cu124、Diffusers 0.38.0、Transformers 4.57.6，RTX 3090 24 GB。
重新安装原生栈后，`yarn doctor:native` 的 CUDA 光栅化前向/反向检查通过。
本轮独立进程重新运行 SD1.5、SDXL、Flux Schnell NF4、AnimateDiff、Wan2.1 Resident、CogVideoX-2B、Shap-E、TRELLIS、MDM，均完成实际推理及文件输出检查。
产物保留在 `.build/model-results/linux-dev-20261106/`，`validation-summary.json` 记录视频逐帧变化、GLB 顶点/三角面及动作轨迹检查，`validation-contact.png` 已人工查看。
本轮未对每个模型重新施加历史 5 GB 主机内存限额；低步数视频仅证明功能可运行，不作为最终质量验收。

修复了 Wan 示例仍引用旧加载器名称、TRELLIS 的 DINOv2 本地参数名与 vendor 不匹配，以及 Shap-E/CogVideoX-2B 在 Torch 2.4 下导入新版 Diffusers 的兼容问题。
桌面真实执行器另有导入顺序问题：site-packages 中的 DiffSynth 覆盖扩展自带版本；server/executor 现在共用扩展根目录优先的导入逻辑。
默认 Python 回归为 372 项，343 项通过、29 项条件跳过。模型推理与默认回归是分别运行的。

真实 AppImage 经 AppRun 启动，在已有独立 GUI 安装环境升级到当前依赖后通过工作流选择、SDK 发现、错误反馈、H.264 播放、GLB 交互加载，以及 Wan 256×256/17 帧/12 步 GPU 推理并在页面播放。
这是安装环境升级重放，不能代替当前版本从全新空目录安装的复验。

StdGEN 的官方权重位置已补齐并固定 revision；规范化（320×512、4 步）和六视图（320×512、40 步、1 层）均完成真实 GPU 推理。测试现检查真实输入对应的结果尺寸、6 张颜色图和 6 张法线图，均非空；产物及人工查看的拼图为 `stdgen-contact.png`。低步数规范化有明显失真，六视图细节也不稳定，仅作为功能冒烟，不作为建模质量验收。
官方 image_encoder 只有 pickle 格式；当前 Transformers 拒绝在 Torch 2.4 读取该格式。需要在独立 CPU 环境安装 Torch >=2.6、safetensors、numpy，运行：

```bash
python scripts/convert_checkpoint_safetensors.py <StdGEN-canonicalize-1024>/image_encoder/pytorch_model.bin
```

转换器只接受 tensor state dict，以 `weights_only=True` 读取并原子写入 `model.safetensors`，不修改推理环境。
StdGEN 的完整 3D 重建、CogVideoX-5B、HunyuanVideo 尚无本轮完成证据；LTX-2.5 当前账号下载返回 HTTP 401/GatedRepoError，需要先获得官方仓库访问授权并在本机登录。

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

上表为合并前依赖环境的留存实测；dev 0.3.0 的 Diffusers/Transformers 版本已经变化，未把旧结果作为新依赖的全量 GPU 验收。

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
