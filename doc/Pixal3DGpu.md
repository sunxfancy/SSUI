# Pixal3D GPU 图生 3D

入口：`examples/advance/workflow-pixal3d.py`。模型是显式输入，准备节点控件时不会装载权重。
前端提供 Pixal3D 模型目录 / Hugging Face ID、低显存模式，以及标准 Mesh 下载输出。
该示例的 `ImageUploader` 保留 PNG 透明蒙版；自定义 Python 工作流可调用
`ssui_3dmodel.Pixal3D.LoadPixal3DImage`。

## 本机验证环境

- Windows ARM64，NVIDIA RTX Spark N1X，计算能力 `sm_121`，CUDA Toolkit 13.4。
- 原生 CPython 3.13.15；NVIDIA 官方 `torch 2.16.0.dev20261026+cu134` 和
  `torchvision 0.30.0.dev20261026+cu134`，来源为
  [NVIDIA 固定版本发布](https://github.com/NVIDIA/pytorch-windows-ci/releases/tag/woa-nightly-20261026-r40304259310)。
- 独立开发环境 `.build/cuda-arm64-venv`。现有 Windows ARM64 CPU lock 和 `.venv` 未替换。
- FlexGEMM、CuMesh、nvdiffrast、o_voxel、NATTEN、OpenCV 均在本机编译为
  `cp313-cp313-win_arm64` wheel。本机 wheelhouse 位于 `.build/pixal3d-gpu/wheels`。
- 实际版本、上游 commit、wheel SHA256 及九项操作探针结果记录在
  [算子验证报告](windows-arm64-cuda-pixal3d-operators.json)。这些本地 wheel 尚未发布，
  也不代表通用安装器已经支持完整 Windows ARM64 CUDA 依赖集。

稀疏卷积探针关闭 TF32，将 GPU FP32 结果与 CPU FP64 稠密卷积参考比较，
并检查首次自动调优和缓存调用的结果一致。

原生构建使用 MSVC ARM64 和 `TORCH_CUDA_ARCH_LIST=12.1`。新版 PyTorch 要求 C++20；
本机适配还包含 NATTEN 的 Ninja 参数、Python 链接目录、MSVC 编译选项和 CUTLASS 类型特征，
以及 o_voxel 的标准 double 字面量和张量形状 `int64_t` 转换。
OpenCV 复用了包合集的 ARM64 配方，关闭 MSMF / FFmpeg / IPP / OpenCL。

## 启动与验收

在仓库根目录的 PowerShell 中选择该独立环境，并保持服务端和执行器使用同一环境：

```powershell
$env:SSUI_VENV_PATH = "$PWD/.build/cuda-arm64-venv"
$env:HF_HOME = "$PWD/.build/pixal3d-gpu/hf-cache"
$env:TORCH_HOME = "$PWD/.build/pixal3d-gpu/torch-cache"
$env:TRITON_CACHE_DIR = "$PWD/.build/pixal3d-gpu/triton-cache"
$env:FLEX_GEMM_AUTOTUNE_CACHE_PATH = "$PWD/.build/pixal3d-gpu/flex-autotune.json"
yarn probe:pixal3d-gpu --output .build/pixal3d-gpu/full-probe.json
```

使用专用端口，避免与日常开发实例冲突：

```powershell
$env:SSUI_SCHEDULER_HOST = '127.0.0.1'
$env:SSUI_SCHEDULER_PORT = '5055'
yarn start:server --host 127.0.0.1 --port 7542
```

另一个继承上述缓存 / Python 环境配置的终端中执行：

```powershell
$env:SSUI_SCHEDULER_URL = 'ws://127.0.0.1:5055/'
yarn dev:executor
```

准备官方模型快照与真实物体图像后：

```powershell
yarn test:pixal3d-gpu-workflow --server http://127.0.0.1:7542 `
  --model .build/pixal3d-gpu/models/Pixal3D `
  --image .build/pixal3d-gpu/input.png `
  --output .build/pixal3d-gpu/acceptance
```

该命令经过 HTTP → 调度器 → 原生 GPU 执行器，检查发现 / 准备 / 执行接口，并通过
`/file` 下载结果，用 trimesh 重新加载、检查有效几何，保存 `mesh.glb` 与 `report.json`。
验收使用手动 30° 相机、1024 分辨率、种子 42、各采样阶段 12 步。

## 输入与辅助权重

- Pixal3D 单图权重：`TencentARC/Pixal3D`，revision
  `b0cb2e1b794cab9aa0ac38a95d794a4d9337437f`。多视图权重不用于本次验收。
- 输入：[官方示例 PNG](https://github.com/TencentARC/Pixal3D/blob/f7cf38429b0bd264f1995f0f8743a88b1c728b94/assets/images/0_img.png)，
  SHA256 `6959e517ee4bc6852791f69bd6ece696a435abcda8321727c07db8daf7f457cf`。
- DINOv3 使用适配器声明的 `camenduru/dinov3-vitl16-pretrain-lvd1689m`。
- NAF 固定为官方 commit `37f2dfc180f2de53d98bd601109c0da0dd6b0f43`，避免启动时
  查询 GitHub 分支验证 API。源码和权重缓存于 `TORCH_HOME`。
- 已有透明蒙版的 RGBA 图像不需要去背景模型。普通 RGB 输入仍使用官方配置的
  `briaai/RMBG-2.0`；该仓库需要用户具备相应访问权限并在环境中完成 Hugging Face 登录。
  空蒙版会明确报错，不继续生成。
- 自动相机估计还需要 MoGe-2；本次固定相机验收不验证该辅助模型。

GPU 注意力默认使用 PyTorch SDPA，仍可通过 `ATTN_BACKEND` / `SPARSE_ATTN_BACKEND`
显式选择其他后端。NAF 的邻域注意力使用实际构建的 NATTEN GPU 算子。

## 完整工作流结果（2026-10-27）

本机已完成上述真实权重的 HTTP 全链路验收：约 379 秒，生成 73,797,760 字节 GLB，
包含 669,038 个顶点、933,746 个三角面和 4096×4096 PBR 纹理。重新加载、通过 HTTP
下载与多视角渲染检查均通过，详见
[工作流报告](windows-arm64-cuda-pixal3d-workflow.json)。

修复了在长时间原生网格调用中发生的 WebSocket 心跳超时。调度器和执行器保留 Ping，
允许延迟 Pong；真正断开连接时，调度器会将关联任务标为失败并唤醒等待中的请求，
避免 HTTP 无限等待。

验证覆盖 1024 分辨率、手动相机、RGBA 输入。1536 分辨率、MoGe 自动相机和需要授权的
RGB 去背景尚未完成真实权重验收。首次自动调优 / 网格重建期间曾观察到约 58GiB GPU
内存占用；本次不据此声称较小显存 GPU 可运行相同导出配置。
