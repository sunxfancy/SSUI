# Mac 模型支持检查

本表依据仓库代码检查，日期：2026-10-28。“已有适配”不等于完成真模型回归。
范围为 SSUI 模型节点及其直接依赖；vendor 中未接入节点的所有实验模型不逐一承诺兼容。

| 模型 | 检查结果 / 本次修改 | 剩余验证或阻塞 |
|---|---|---|
| SD1 / SDXL | 已通过 `backend.util.devices.TorchDevice` 选择 MPS / CPU | 需权重与端到端生成回归 |
| FLUX | 已有 MPS 精度及 RoPE 适配 | bitsandbytes NF4 / INT8 路径不能等同于 Mac 支持；当前测试清单恰好使用这些量化权重，需另设非 bnb 的 Mac 回归 |
| OmniGen2 | vendored 实现已有 MPS 分支 | 不能据此保证全部 attention 后端或节点链路可用；需真实推理 |
| AnimateDiff | **本次移除节点 CUDA 写死**，沿用统一设备选择；CPU 默认 float32，MPS 默认 float16 | 已在 16GB Mac 上用真实 DreamShaper 8 + AnimateDiff v2 权重完成 256×256 和 512×512、8 帧、20 步生成及 MP4 校验；更大尺寸/长视频仍需按内存验证 |
| CogVideoX-5B | **本次统一 manager 的设备与精度**；原先只覆盖 `load_models`，管线仍读取 manager 默认配置 | 真实 MPS attention / 3D 卷积、完整小型 DiT（含切片、逐层卸载）已通过；独立官方 Diffusers 入口已完成真实 5B 权重生成（128×128、9 帧、4 步）；原 vendored 节点仍仅完成小型测试 |
| Wan 2.1 T2V-1.3B | **独立低内存入口已跑通完整真实权重生成**，UMT5/DiT/VAE 分进程运行 | 16GB Mac 实测 256×256、9 帧、30 步；后续帧有模糊重影；未验证高分辨率或长视频 |
| Wan 2.1 Fun / 14B | **已补设备选择与 MPS 实数 RoPE**，现代 MPS 默认 BF16、旧系统及 CPU 使用 float32；修复旧管线的 patchify 返回值解包 | 小型 DiT 与管线前向已通过 CPU/MPS 数值比较；完整 VAE、文本编码及真实权重生成仍待验证 |
| Wan 2.2 TI2V / A14B | **已接入设备选择、实数 RoPE、MPS 内存管理及 LayerNorm** | TI2V-5B 已通过真实权重 MPS 文生视频：128×128、5 帧、4 步，独立分阶段入口；A14B、图生视频和高级 S2V/VAP 尚未验证 |
| HunyuanVideo T2V / I2V | **已移植基础 MPS 推理路径**，权重暂存 CPU，Linear/RMSNorm/Conv3D 在 MPS 计算 | 已补节点设备/精度、DiT 逐层卸载、MPS autocast 兼容及空 padding attention；真实 MPS FP32/BF16 层测试与完整小型 DiT 前向通过。独立官方 Diffusers 入口已完成真实 T2V 权重与 VAE 生成（128×128、9 帧、4 步）；原节点及 I2V 仍待完整验证 |
| MiniMax H3 | **真实 T2VA CLI 已完成 MPS 音视频生成**：逐权重磁盘读取，128×128 / 124 帧 / 24 fps，约 149 秒 | 低步数样片为模糊纹理，非质量验证；原有常驻 CPU 权重卸载曾伴随 watchdog 重启。仅验证当前低内存路径与参数，I2V/ref2va 和 UI 未完整验证；int8/NF4 不兼容 MPS |
| LTX-2.5 | **固定官方 MPS 实现已接入**：小型视频 DiT 与 Apple fused SDPA 对比通过 | 真实蒸馏模型 CLI 已完成 MPS 音视频生成：128×128 / 9 帧 / 24 fps；词嵌入卸载、投影分块、磁盘逐层加载。样片为草地纹理，未清晰呈现提示词中的猫，不能视为质量达标 |
| TripoSR（新增） | **完整图像转彩色 GLB 已通过**，MPS float32 推理 + CPU 网格提取 | 16GB Mac、64³、真实椅子图片；不含 UV 烘焙，复杂背景需预处理 |
| TRELLIS image-large | **真实权重的 MPS 网格生成已跑通**：稀疏卷积、池化、SDPA 和 FlexiCubes 适配 | 整数邻接映射使用 Metal，去重/计数使用 MPS；顶点颜色 GLB 已导出；UV 烘焙、Gaussian/RF 渲染和其他实验分支尚未移植 |
| StdGEN（vendor） | **未移植**：`RasterizeCudaContext` 等 CUDA 渲染路径 | 需要替代渲染后端；没有发现对应正式 SSUI 节点 |
| NVIDIA Kimodo | **SOMA-RP-v1.1 文本转动作已跑通**：逐层 MPS LLM2Vec + MPS 动作网络 | 16GB Mac，2 秒 / 60 帧 / 20 步，NPZ/BVH；文本基座使用固定社区合并版，未验证全部 G1/约束/原生后处理路径 |
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
Wan 2.2 TI2V-5B 和 Wan 2.1 T2V-1.3B 已分别通过独立分阶段流程。

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
当前入口是独立脚本，原有 Fun/14B 节点及 Wan 2.2 A14B 仍需分别验证。

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

## 2026-10-28 视频 MPS 补充验证

- Hunyuan 移除构造器的 CUDA 分配及 RMSNorm 卸载层内写死的 CUDA；缓存释放按设备处理。
- Torch 2.4 的 MPS 路径使用显式精度转换，不调用不支持的 MPS autocast；时间编码在输入设备计算。
- 完整小型 Hunyuan DiT（一个双流块、一个单流块）在 MPS BF16 上与 CPU FP32 对比通过；这不是完整权重生成验证。
- 修复文本恰好填满 token 窗口时空 attention 分支及 `-0` 切片问题。
- Wan 1.3B 的 UMT5 embedding 查表也移到 MPS；使用已有固定版本权重，完成 128×128、5 帧、8 步的 MPS 文本编码、去噪和 VAE 解码，MP4 编解码校验通过。产物为 `output/wan-mps-regression/wan.mp4`，约 43 秒；这是流程回归样例，不代表成片质量。
- CPU 仍负责文件读取、权重暂存、兼容 Torch 2.4 的初始随机噪声生成和视频编码；没有启用 MPS 不支持算子的 CPU 回退。16GB 统一内存仍出现系统 swap，完整大型模型不可据此认为能装入内存。

后续验证进展见下节，以上为前一次实测记录。

## 后续移植与真实权重验证

- Wan 2.2 TI2V-5B：固定 `921dbaf3f1674a56f47e83fb80a34bac8a8f203e`，下载约 23GB 权重并以文件映射暂存，MPS BF16 逐层去噪、MPS FP32 VAE 解码。128×128 / 5 帧 / 4 步已导出 `output/wan22-mps/wan22.mp4`；文本约 15.5 秒、去噪约 183.2 秒、解码约 5.9 秒。低步数样例呈现抽象/模糊画面，不能代表正常生成质量。
- CogVideo：补齐分阶段加载和 DiT 层级卸载，显式指定切片计算设备；完整小型 DiT 和切片路径已在 MPS 对比通过。另用固定官方 Diffusers 环境完成真实 CogVideoX-5B 生成：128×128 / 9 帧 / 4 步，约 222.1 秒，产物 `output/cogvideo-mps/cogvideo.mp4`。短视频要求至少 9 帧且为 8n+1，避免 VAE 时间上采样输出帧数不匹配。
- H3：固定新版 diffusers，runner 支持 MPS 逐层 Accelerate offload，音视频联合小型 DiT、视频 VAE 逐层卸载、音频 VAE 均通过 CPU/MPS 对比。音频 VAE 的 weight_norm 不兼容 leaf offload，因此约 0.6GB 音频权重常驻 MPS；不支持 CUDA int8/NF4 权重。
- LTX：固定官方原生 MPS 实现并安装 `mps-sdpa`，完整小型视频 DiT 和 Apple fused attention 对比通过；修正蒸馏 CLI 负面提示词参数，默认不用 FP8；HF 许可及五个固定权重下载已完成。磁盘卸载缩为一个 CPU 和一个 MPS 缓冲、关闭预取后，后续将 Gemma 词嵌入用后卸载、禁用生成 KV cache、投影按 64 token 分块，并过滤去噪模型不使用的连接器权重，已完成真实 MPS 提示词编码、8+3 步两阶段去噪、上采样、音视频解码及 MP4 导出。产物 `output/ltx-mps/ltx.mp4`，128×128 / 9 帧 / 24 fps；独立 CLI 验证，不等于 SSUI 节点 UI 端到端验证。
- Hunyuan：大型 PyTorch checkpoint 使用 mmap 加载，并保留旧格式兼容；另用固定官方 Diffusers 环境完成真实 T2V 权重生成：128×128 / 9 帧 / 4 步，约 464.5 秒，产物 `output/hunyuan-mps/hunyuan.mp4`。
- 独立环境与入口：`dependencies/requirements-video-mps.txt`、`yarn test:video:external-mps`；环境 `pip check` 通过。

CogVideo/Hunyuan 的报告逐阶段确认文本、去噪及解码张量位于 MPS，禁用算子 CPU fallback。4 步样例主要呈现色块，是完整计算流程验证，不是正常成片质量或原 SSUI vendored 节点的端到端验证。

## H3 完整测试的限制

完整 H3 测试期间系统出现 watchdog 超时重启；系统报告显示内存压缩区 segments
达到上限及 43 个 swapfiles，不能将此前的逐层 CPU offload 宣称为 16GB Mac 可用。
后续改为每层从 safetensors 按需读取，避免保留完整 CPU state dict；小模型混合精度
数值对比已通过。另限制 MPS 分配、逐块同步，并检查系统可用内存与 swap 增量。
用户随后明确要求恢复完整 H3 验证。新增独立父进程监控，覆盖权重加载和推理全过程，
可用内存低于 1.5 GiB 或 swap 增长超过 2 GiB 时终止子进程。
新磁盘读取路径已于 2026-11-03 完成真实 T2VA CLI：128×128 / 124 帧 / 24 fps，
生成约 149 秒，MP4 读回确认视频尺寸、帧数以及 32 kHz 音频。
`--steps 2` 是最低测试参数，调度器实际调用 DiT 1 次；样片仅呈现模糊的绿/橙色纹理，
不能视为正常生成质量或所有分辨率下的稳定性证明。

完整管线要求 5–15 秒，最短对齐长度为 124 帧；22 帧只适用于小型 VAE 测试，
不能用于完整 H3。冒烟脚本已在启动模型前校验帧数范围 124..345 且为 17n+5。
产物：`output/h3-mps/h3.mp4`；完整日志：`run-124frames.log`；MPS/有限值报告：
`h3.mp4.json`；媒体校验：`media-validation.json`。小型音视频 DiT、磁盘卸载和
音视频 VAE 数值测试通过（`preflight-tests.log`），保护及 runner 的 9 项回归通过
（`guard-tests.log`）。

LTX 冒烟入口保留独立进程内存监控：可用内存低于 1.5 GiB 或 swap 增长超过
2 GiB 时终止子进程，并报告具体数值。未关闭 MPS 分配上限，也未启用 CPU 算子回退。
早期日志为 `output/ltx-mps/run-bounded.log` 与 `run-trimmed.log`；两次均以异常退出。
后续优化日志见 `output/ltx-mps/run-filtered.log`，最新进展如下。

### LTX 内存优化验证（2026-11-03）

- Gemma 输入词嵌入约 1.88 GiB，与未使用的 lm_head 共享主机权重；查表仍在 MPS，
  用后卸载。保留全部所需 hidden states，关闭仅生成需要的 KV cache。
- 退出文本编码阶段时释放 Accelerate 主机副本及流式缓冲池。
- 特征投影使用 CPU 权重存储、逐层 MPS 计算；V2 的逐 token RMS 与投影按 64 token 分块。
- 流式加载只读取当前模型 state dict 中的非块参数/持久缓冲，避免重复加载外部连接器。
  真实去噪模型非块权重由 317 个筛到 59 个。
- 小型 Gemma 和音视频双路特征投影已通过 FP32/BF16 的 MPS/CPU 对比，覆盖重复批量编码、
  左右 padding 与非整块尾部；BF16 CPU 对比使用 0.02 容差，MPS 编码前后使用 0.005。
  验证命令：`SSUI_VENV_PATH="$PWD/.venv/video-mps" yarn test:video:external-mps --ltx-memory-only`。
- 完整 Gemma 第 40 层观测到 MPS 张量约 0.78 GiB、驱动分配约 3.13 GiB。
  保持 0.35 MPS 内存分配比例及独立系统内存保护，不启用 CPU 算子回退。

完整结果：`output/ltx-mps/run-filtered.log` 退出码 0；`ltx.mp4.json` 报告 MPS、
9 帧和 128×128，记录 18,802 次 Linear 及卷积/词嵌入的 GPU 执行。
`media-validation.json` 确认视频为 24 fps，音频可解码为 48 kHz / 15,840 samples。
报告单调时钟耗时约 599 秒，yarn 墙钟约 1118 秒，不将这次运行用作严格性能基准。
`embedding-test.log` 的 FP32/BF16 对比及含多余权重的双层单缓冲流式加载对比均通过；
`runner-tests.log` 的 7 项回归通过。`preview.png` 主要显示草地纹理，没有清晰的猫；
这是极低分辨率下的完整执行验证，不代表提示词遵循或成片质量达标。
