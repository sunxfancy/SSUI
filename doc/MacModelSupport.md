# Mac 模型支持检查

本表依据仓库代码检查，日期：2026-10-27。“已有适配”不等于完成真模型回归。
范围为 SSUI 模型节点及其直接依赖；vendor 中未接入节点的所有实验模型不逐一承诺兼容。

| 模型 | 检查结果 / 本次修改 | 剩余验证或阻塞 |
|---|---|---|
| SD1 / SDXL | 已通过 `backend.util.devices.TorchDevice` 选择 MPS / CPU | 需权重与端到端生成回归 |
| FLUX | 已有 MPS 精度及 RoPE 适配 | bitsandbytes NF4 / INT8 路径不能等同于 Mac 支持；当前测试清单恰好使用这些量化权重，需另设非 bnb 的 Mac 回归 |
| OmniGen2 | vendored 实现已有 MPS 分支 | 不能据此保证全部 attention 后端或节点链路可用；需真实推理 |
| AnimateDiff | **本次移除节点 CUDA 写死**，沿用统一设备选择；CPU 默认 float32，MPS 默认 float16 | 已在 16GB Mac 上用真实 DreamShaper 8 + AnimateDiff v2 权重完成 256×256 和 512×512、8 帧、20 步生成及 MP4 校验；更大尺寸/长视频仍需按内存验证 |
| CogVideoX-5B | **本次统一 manager 的设备与精度**；原先只覆盖 `load_models`，管线仍读取 manager 默认配置 | 真实 MPS attention / 3D 卷积已通过；完整 CogVideo 权重生成尚未验证 |
| Wan 2.1 T2V-1.3B | **独立低内存入口已跑通完整真实权重生成**，UMT5/DiT/VAE 分进程运行 | 16GB Mac 实测 256×256、9 帧、30 步；后续帧有模糊重影；未验证高分辨率或长视频 |
| Wan 2.1 Fun / 14B | **已补设备选择与 MPS 实数 RoPE**，现代 MPS 默认 BF16、旧系统及 CPU 使用 float32；修复旧管线的 patchify 返回值解包 | 小型 DiT 与管线前向已通过 CPU/MPS 数值比较；完整 VAE、文本编码及真实权重生成仍待验证 |
| Wan 2.2 TI2V / A14B | **已接入设备选择、实数 RoPE、MPS 内存管理及 LayerNorm** | 随机初始化小型 DiT 的 BF16 前向、CPU 数值比较和逐层卸载已通过；完整 TI2V/A14B 权重、VAE、文本编码和高级 S2V/VAP 路径尚未验证 |
| HunyuanVideo T2V / I2V | **本次删除导入时设置 CUDA 显存比例的副作用**，无 CUDA 不再因这一行失败；推理仍未移植 | 节点及 DiT 的 offload 路径仍写死 CUDA，还需处理随机数设备和 autocast |
| MiniMax H3 | **未移植**：`ssui_video/h3_runner.py` 的加载、VAE、自动 offload 写死 CUDA | 独立运行环境及其模型栈需单独适配 |
| LTX-2.5 | **未确认 Mac 支持**：通过独立环境调用外部管线 | 当前仓库不含该外部实现；跳过 natten 安装不代表能在 MPS 推理 |
| TripoSR（新增） | **完整图像转彩色 GLB 已通过**，MPS float32 推理 + CPU 网格提取 | 16GB Mac、64³、真实椅子图片；不含 UV 烘焙，复杂背景需预处理 |
| TRELLIS image-large | **真实权重的 MPS 网格生成已跑通**：稀疏卷积、池化、SDPA 和 FlexiCubes 适配 | 整数邻接映射使用 Metal，去重/计数使用 MPS；顶点颜色 GLB 已导出；UV 烘焙、Gaussian/RF 渲染和其他实验分支尚未移植 |
| StdGEN（vendor） | **未移植**：`RasterizeCudaContext` 等 CUDA 渲染路径 | 需要替代渲染后端；没有发现对应正式 SSUI 节点 |
| CosyVoice | vendor 有无 CUDA 时回退 CPU 的逻辑 | CPU 路径不代表 MPS 加速，TensorRT 路径仍需 CUDA |
| Qwen | 节点使用 Transformers `device_map="auto"`，未强制 CUDA | 需验证具体权重的远程模型代码、精度及设备映射；不能直接归类为 CUDA-only |

## 本次验证

已在当前工作树创建独立 `.venv`，通过 `yarn update-lock:no-upgrade` 和
`yarn install-requirements` 安装完整 Mac 锁文件（151 个基础包）及可编辑 SSUI。
新增显式依赖：ModelScope、imageio/FFmpeg、SentencePiece、ftfy、pandas。
Torch 保持 2.4.1，Transformers 保持 4.46.2；未修改其他工作树环境。

修复 Qwen Image 文本编码器的提前导入：旧 Transformers 不再阻断全部 DiffSynth。
真正使用 Qwen Image 时，仍需要具备 Qwen2.5-VL 支持的兼容环境。

验证命令：

```sh
yarn test_on video_device_test
SSUI_RUN_VIDEO_RUNTIME_TESTS=1 yarn test_on video_runtime_test
```

设备契约测试隔离大模型下载。运行时测试启动独立进程，避免旧测试的假模块掩盖错误：
导入真实 DiffSynth、Wan 2.2 管线和六个视频节点；在实际 MPS 上运行 attention、
CogVideo Conv3D、实数 RoPE、随机初始化小型 Wan DiT 及 Wan 2.1 管线前向，
并比较 CPU/MPS 数值；额外验证 Wan 2.2 新管线 BF16 前向及两种内存预算下的逐层加载/卸载，禁止测试路径调用 CUDA 内存 API；完成 FFmpeg 编码/解码回环。另已下载并校验约 3.7GB 的
DreamShaper 8 / AnimateDiff v2 真实权重，完成 AnimateDiff 节点的端到端视频生成。
沙箱会隐藏 MPS 或阻断 OpenMP 共享内存，真实 GPU 检查需在允许访问硬件的环境执行。

依赖检查的已知例外：`pip check` / `uv pip check` 报 mediapipe 0.10.21 平台标签不匹配。
该包 WHEEL 元数据写为 x86_64，但实际扩展二进制包含 arm64 和 x86_64，
当前 Apple Silicon 上真实导入成功。未篡改第三方 wheel 元数据，依赖检查不能宣称全绿。

## 真实 AnimateDiff 流程

`yarn test:video:smoke` 负责固定版本下载和 SHA-256 校验、调用真实节点、编码 MP4、
解码验证帧数与尺寸，并保存预览和 JSON 报告。`--workflow` 会通过 SSUI 的沙盒
加载器执行 `examples/advance/workflow-video-mac.py`；准备配置阶段不加载模型。

已完成 128×128 / 4 帧 / 4 步（生成约 12 秒）和 256×256 / 8 帧 / 20 步
（生成约 50 秒，加载约 2.3 秒）。256 像素结果能辨认湖面、山景和帆船；8 帧之间有变化，
但只是一段 2 秒短样例，不代表长视频质量或其他模型通过。产物在 `output/video-mac-preview/`。

另已通过 SSUI 沙盒工作流入口完成 512×512 / 8 帧 / 20 步生成，工作流执行（含加载）
约 182 秒，全命令约 187 秒。产物在 `output/video-mac-workflow/`：MP4、四帧预览和
含版本、参数、耗时的 JSON 报告。画面可辨认帆船与山景，帧间变化较轻微；未验证长时运动。

修复项还包括 MPS Generator 兼容、两个生成阶段统一 seed、原测试清单无效的
DreamShaper URL，以及真模型测试改为独立进程，避免被工作流假模块替代。

```sh
yarn test:video:smoke --download-only
yarn test:video:smoke --local-files-only --workflow --device mps --size 256 --frames 8 --steps 20
SSUI_RUN_MODEL_TESTS=1 SSUI_VIDEO_MODEL_DIR="$PWD/models/video-smoke" yarn test_on model.diffsynth_model_test
```

其余模型仍按上表作为未完成事项，不把 AnimateDiff 的成功推广到全部模型。

## Wan 的 MPS 精度与内存管理

Wan 2.1 / 2.2 使用统一运行时策略：macOS 14+ 的 MPS 默认 BF16，可显式选择
float32；更旧系统回退 float32。拒绝 MPS float16，以避免 UMT5 溢出。
当前 Torch 2.4.1 缺少 MPS autocast，归一化显式转 float32 计算后恢复输入精度。

新管线按设备查询内存和清理缓存。Torch 2.4.1 没有 `recommended_max_memory`，
此时以物理内存的一半作为 MPS 权重驻留预算；这只是保守策略，不是内存上限保证。
CPU 权重与 MPS 共用物理内存，逐层卸载不能让任意大小的模型适配 16GB Mac。
Wan 2.2 完整权重仍未验证；Wan 2.1 T2V-1.3B 已通过下面的独立分阶段流程。

## 16GB Mac 的 Wan 1.3B 实测

`yarn test:wan:smoke --local-files-only` 使用默认 256×256、9 帧、30 步、8fps。
首次运行需去掉 `--local-files-only` 或先运行 `--download-only`。官方权重固定版本
`37ec512624d61f7aa208f7ea8140a131f93afc9a`，三份权重均通过 SHA-256 校验。

脚本使用文件映射、meta 初始化、逐层 UMT5 转移，并以三个子进程隔离文本编码、
BF16 去噪和 float32 VAE 解码。没有同时驻留三个模型，也没有用随机模型替代权重。
MPS 对五维张量的全量归约会触发原生断言，因此非有限值检查先展平张量。

实测文本编码约 13 秒，去噪（含加载）约 58 秒，VAE 解码约 10.5 秒；
完整命令（含校验和进程启动）约 97 秒。MP4 解码后确认 9 帧、256×256，
预览可辨认橘猫在草地行走，后几帧模糊重影；128 像素 / 8 步只生成色块，未采用。
产物和报告在 `output/wan-mac-preview/`。

最高单进程 RSS 约 8.24GiB，不代表 GPU 与系统总峰值。
采样的系统可用内存最低约 2.35GiB，系统交换空间从约 5.05GiB 增至 6.40GiB；
这两个系统指标包含其他应用影响，不能将交换空间全部归因于生成进程。
当前入口是独立脚本，原有 Fun/14B 节点及 Wan 2.2 的整条链路仍需分别验证。

## 3D 工作流

新增 `examples/advance/workflow-3d-mac.py` 的 `img2mesh_mac`，采用固定版本 TripoSR。
`yarn test:3d:smoke --local-files-only --device mps` 从实际 SSUI 沙盒工作流完成图像重建、
GLB 导出、重新载入及三个视角预览。完整说明见 `extensions/3D-Model/README.md`。
TripoSR 的结果与 TRELLIS 独立；TRELLIS 新进展见下文，StdGEN 尚未移植。

## TRELLIS GPU 路径

新增 `torch` 稀疏后端保留 spconv 权重布局，特征运算使用 MPS；邻接索引由 Metal 构建，
统计及去重整数拓扑使用 MPS，CPU 仅处理少量动态尺寸元数据。真实 DINOv2 编码、稀疏结构采样（10,828 体素）、SLAT 和网格解码
已产出椅子 GLB：228,766 顶点、455,764 面。已检查三个视角；网格非闭合，有局部碎片和孔洞。
通过 CPU/MPS 卷积、分批/窗口注意力和完整小型 SLatFlow 数值对比，未测量 GPU 利用率百分比。
入口为 `yarn test:trellis:smoke`，SSUI 节点入口 `--workflow`；详见 3D 扩展 README。

TRELLIS SSUI 工作流复测已通过：两阶段各 8 步，节点约 176 秒、总命令约 180 秒。
交付文件 `output/trellis-mac-workflow/mesh.glb`；79 项回归中 68 通过、11 跳过。


TRELLIS 整数拓扑 GPU 移植已追加实测：69 万点邻接构建从 1777 ms 降到 51 ms，
554 万行坐标去重从 4545 ms 降到 145 ms，计数从 5.27 ms 降到 1.89 ms。
这些是同步计时的三次中位数，排除首次 Metal 编译及邻接缓存。
同一 SLAT 的正常网格解码阶段约 49.24 秒，CPU 拓扑对照约 66.83 秒（各单次）；
面索引完全一致，顶点最大误差 1.19e-7，8 位颜色最大差 1。
已修复 Torch 2.4 MPS 的大整数排序及超过 2²⁴ 扁平索引精度问题；
详细方法和复现命令见 `extensions/3D-Model/vendor/trellis/MPS_PORT.md`。
