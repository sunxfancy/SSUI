# 自动部件分割与四边面重拓扑（第一版）

打开 `examples/basic/workflow-retopology.py`。模型输入支持 GLB、OBJ、PLY、STL；
推荐 GLB（可携带场景变换）。上传后运行，两个输出分别显示分割部件与重拓扑结果。
预览可拖动旋转、缩放、单独显示部件，并显示网格边。大模型预览会抽样。

## 环境配置

1. 安装独立 [QuadriFlow](https://github.com/hjwdzh/QuadriFlow)，设置
   `SSUI_QUADRIFLOW_EXECUTABLE` 为 `quadriflow` / `quadriflow.exe` 的绝对路径，
   或把该程序加入 PATH。此流程不需要 Blender。
   上游支持 CMake 构建，依赖 Boost、Eigen；按官方 README 编译，不使用 Blender 插件版。
2. 下载官方 [Hunyuan3D-Part](https://github.com/Tencent-Hunyuan/Hunyuan3D-Part)，
   按 `P3-SAM/README.md` 在独立环境安装 Sonata、PyTorch/CUDA 和 chamfer3D 等依赖。
   官方测试环境为 Python 3.10、PyTorch 2.4.0、CUDA 12.1；建议 Linux/WSL GPU 环境验证。
3. 设置 `SSUI_P3SAM_ROOT` 为包含 `demo/auto_mask.py` 的 `P3-SAM` 目录；
   设置 `SSUI_P3SAM_PYTHON` 为该环境的 Python 可执行文件绝对路径。
   可通过 `SSUI_P3SAM_CHECKPOINT` 指定权重；未设置则使用官方加载逻辑。
4. 启动 SSUI server/executor 前设置这些环境变量。P3-SAM Python 与 SSUI 必须能访问
   同一套输入输出绝对路径；Windows 主进程不能直接将 Windows 路径传给 WSL Python，
   全部运行在 WSL 时可直接使用 Linux 路径。Windows executor 也可通过
   `SSUI_P3SAM_WSL_DISTRO` / `SSUI_QUADRIFLOW_WSL_DISTRO` 调用对应的 WSL 环境；
   桥接层自动转换 Windows 盘符路径，保留带空格的路径。

PowerShell 配置示例（路径替换为本机安装位置）：

```powershell
$env:SSUI_QUADRIFLOW_EXECUTABLE = 'C:\tools\QuadriFlow\quadriflow.exe'
$env:SSUI_P3SAM_ROOT = 'D:\models\Hunyuan3D-Part\P3-SAM'
$env:SSUI_P3SAM_PYTHON = 'D:\envs\p3sam\python.exe'
$env:SSUI_P3SAM_CHECKPOINT = 'D:\models\Hunyuan3D-Part\P3-SAM\weights\p3sam.safetensors'
```

不自动下载或安装 GPU 依赖；缺少配置会明确报错。模型及第三方算法许可证以各自上游为准。

## 工作流与产物

- `SegmentParts` 在独立进程调用真实 P3-SAM AutoMask，使用其返回的处理后网格及逐面标签，
  保留未分配区域，按标签创建独立对象，以不同颜色显示。
- `QuadRemesh` 直接逐部件调用独立 QuadriFlow CLI。目标面数按输入面数分配，是近似预算，
  每个部件最少请求四个面。保护边界与锐边，失败时明确报错，不替换为减面算法。
- 下载 `retopology.obj` 可保留四边面；GLB 用于交换，会三角化。
  四边面 OBJ 和网格预览直接使用 CLI 输出的多边形数据，避免经过 trimesh 后丢失四边面。
  合并 OBJ 时保留部件对象，并重新偏移顶点索引；GLB 独立生成三角化副本。
- `report.json` 记录后端名称及各部件输入/输出面数、四边面数。
- `SSUI_3D_OUTPUT` 可指定产物目录，默认 executor 当前目录的 `output/`，每次使用唯一子目录。

第一版不进行隐藏表面生成、自动封口、UV/纹理烘焙、绑定或动画环线修复。
分割边界可能开放或非流形，此时需先修复后重试。部件颜色用于分割可视化，原始纹理不保留。

## 验证

根目录运行 `yarn test_on retopology_test`；设置 `SSUI_QUADRIFLOW_EXECUTABLE` 时还会执行
真实独立 QuadriFlow 球体重拓扑，并检查 OBJ 包含四边面。默认单元测试不加载 GPU 模型。
完整验收需配置 P3-SAM 后，用真实模型运行示例并核对部件、轮廓与下载产物。

## 首轮 CPU 验证记录（已由下面的原生 ROCm 配置替代）

本机 GPU 为 AMD Radeon AI PRO R9700。P3-SAM 上游 CUDA spconv 无法在现有
Windows ROCm 环境加载，因此安装了独立的 **WSL Ubuntu CPU 环境**，没有修改
SSUI 共享环境的 PyTorch。此配置不使用 AMD GPU 加速。

- QuadriFlow 源码：`.build/retopology/QuadriFlow`，提交 `810b7a0967c35b0dc85b4464e3835e26a756c967`。
  可执行文件：WSL 路径下的 `.build/retopology/quadriflow-linux/quadriflow`。
  使用 Boost 1.90、Eigen 3.4、GCC 15、`BUILD_FREE_LICENSE=ON` 编译。
- P3-SAM 源码：`.build/retopology/Hunyuan3D-Part`，提交 `e96be065375438962375b55326416291342958a7`。
- Python：WSL `/home/xiaofans/.ssui/retopology/p3sam-cpu/bin/python`，Python 3.11、
  PyTorch 2.4.1+cpu、torchvision 0.19.1+cpu、spconv 2.3.8、torch-scatter 2.1.2+pt24cpu。
- 官方 Sonata / P3-SAM 权重缓存位于 WSL 用户目录的 `.cache/sonata` 和 `.cache/p3sam`。
- 本地路径和参数已保存至忽略版本控制的 `.ssui-dev.json`，通过 `yarn` 启动的
  server / executor 会读取配置。该 CPU 配置现已被原生 ROCm 配置覆盖。

CPU 兼容处理通过 `scripts/setup_p3sam_cpu.py <Hunyuan3D-Part目录>` 应用于本地源码：
显式选择 CPU、启用 Sonata 内置普通注意力、修复权重缓存目录、让上游采样参数生效。
`p3sam_cpu.py` 把 spconv 的融合 bias 改为卷积后相加，保持网络参数不变。
`tests/p3sam_cpu_kernel_check.py` 已将该路径与密集卷积数值结果比较验证。

实测模型采用上游 `P3-SAM/demo/assets/1.glb`（499,588 个三角面），使用真实模型权重，
采样 10,000 点、64 个提示点、提示批量 4，固定随机种子 42，分出 6 个部件。
目标 2,000 面时得到 1,572 个四边面（四边面比例 100%），
浏览器上传后运行后端处理约 44 秒。低采样配置用于流程验证，精细分割可提高到上游默认的
100,000 点 / 400 提示点，但 CPU 耗时会增加。

复现后端完整流程：

```powershell
node dependencies/venv.cjs python scripts/validate_retopology.py .build/retopology/Hunyuan3D-Part/P3-SAM/demo/assets/1.glb --faces 2000
```

证据保存在 `output/retopology-validation/`：`validation.json`、`preview-payloads.json`，
各次运行的子目录包含分割 GLB、四边面 OBJ、GLB、预览 JSON 和报告。

浏览器验证使用真实的 `UploadLoader` / `MeshArtifact` 组件及 `/files/upload`、`/file`
服务端路由，在本地验收页面运行，并非整套 Tauri 桌面端的自动化测试。
证据为 `browser-payloads.json`、`browser-validation.json`、`pipeline-browser.png`，
`browser-downloads/` 中保存了从浏览器实际下载并逐个核对 SHA256 的 OBJ、GLB、报告和预览数据。

几何检查结果保存于 `geometry-validation.json`：所有坐标有限、非流形边 0 条；
分割后部件共含 292 条开放边，GLB 中有 75 个零面积三角面。保留四边面并不表示模型已满足
生产质量要求，当前样例仍需局部边界与退化面清理。
双向各采样 30,000 个表面点的近邻距离 P95 为包围盒对角线的约 1.52%，
这是采样近似值，不是精确 Hausdorff 距离。

CPU kernel 数值验证（WSL 中执行）：

```bash
/home/xiaofans/.ssui/retopology/p3sam-cpu/bin/python /mnt/c/Users/xiaofans/.codex/worktrees/c92b/SSUI/tests/p3sam_cpu_kernel_check.py
```

## Windows 原生 ROCm（当前默认，2026-10-28）

当前 `.ssui-dev.json` 已切到 Windows 原生进程：

- GPU：AMD Radeon AI PRO R9700（gfx1201，32 GB），PyTorch 2.9.1+rocm7.2.1。
- 独立环境：`.build/retopology/p3sam-rocm-env/Scripts/python.exe`。
  共享只读的现有 ROCm PyTorch，重编译的包安装在独立环境中，不覆盖 SSUI 的共享包。
- 稀疏算子：从 Windows ROCm FlexGEMM 源码重新编译的 HIP 内核，配合 ROCm GEMM。
  源码提交 `148d4c7b186795665a9feb72f0def85c155cb886`。
- CSR 算子：从 torch-scatter 上游源码 HIP 编译的 Windows wheel，
  上游提交 `f514c10f920b5aeed2eb162092f0ad20d3edee52`，本地版本 `2.1.2+rocm72`。
- 注意力：PyTorch ROCm GPU SDPA，保持 Sonata 的 packed attention 接口。
- QuadriFlow：`.build/retopology/quadriflow-windows/Release/quadriflow.exe`，
  Visual Studio 2026 / MSVC 编译的 Windows 可执行文件。
- 权重：`.build/retopology/weights/sonata.pth` 与 `p3sam.safetensors`，已复制到 Windows。
  推理与重拓扑均不启动 WSL，也不执行 CPU 模型推理。

上游 spconv/cumm 的生成器包含 NVIDIA 专用 PTX，没有可直接启用的完整 HIP 后端。
`p3sam_rocm.py` 因此只适配 Sonata 推理实际使用的 `SparseConvTensor`、`SubMConv3d`，
映射到上述已源码编译的 HIP 稀疏算子，并保持 checkpoint 的 KRSC 权重布局。
这不等同于移植整个 spconv/cumm，也不支持训练或任意 SpConv 网络。

重编译与数值验证入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_p3sam_rocm.ps1 -RuntimeVenv C:/Users/xiaofans/Workspace/Agents/SSUI/.venv -DevelInclude C:/Users/xiaofans/Workspace/Agents/SSUI/.build/rocm-devel-headers
```

源码放置于 `.build/retopology/FlexGEMM` 和 `.build/retopology/pytorch_scatter`。
wheel 产物位于 `.build/retopology/wheels/`，完整编译日志为同级的
`flexgemm-rocm-build.log`、`scatter-rocm-build.log`。
`tests/p3sam_rocm_kernel_check.py` 已在实际 GPU 上验证稀疏卷积、邻接缓存复用、
CSR sum/mean/min/max 和变长注意力；卷积最大绝对误差约 `1.2e-7`，
半精度注意力最大绝对误差约 `4.8e-4`。

`SSUI_P3SAM_BACKEND=rocm` 启用这一适配路径，`SSUI_P3SAM_DEVICE=cuda` 是 PyTorch HIP
沿用的设备命名，实际设备为 AMD GPU。`SSUI_SONATA_CHECKPOINT` 与
`SSUI_P3SAM_CHECKPOINT` 分别指定本地权重；P3-SAM 源码通过
`scripts/setup_p3sam_rocm.py` 处理本地权重加载和上游覆盖采样参数的问题。

GPU kernel 验证报告及真实模型结果保存于 `output/retopology-rocm-validation/`。
分割 JSON 的 `runtime` 字段记录实际 GPU 名称、HIP 版本和峰值显存。

全原生实测使用相同的 499,588 面官方模型，采用上游默认的 100,000 个采样点、
400 个提示点（批量 4），得到 23 个部件、3,982 个四边面。分割约 118 秒，
包括 Windows 原生 QuadriFlow 的全流程约 130 秒，GPU 峰值显存约 6.50 GiB。
不应与前面的低采样 CPU 测试直接作速度比较。
清理前结果有 902 条开放边、66 个退化 GLB 三角面，非流形边为 0；
双向表面采样近邻距离 P95 约为包围盒对角线的 1.03%。

### 导出质量清理

重拓扑现在逐部件选择有效的四边面三角化对角线，移除完全零面积的面，
并对塌缩边做有界的局部平滑。每个顶点相对原坐标的移动上限为部件包围盒
对角线的 0.005%；若仍不能生成有效三角面，任务明确失败。
导出后重新读取实际 float32 GLB，检查有限坐标及退化三角面，防止精度转换引入塌缩。
OBJ 保留四边面，原始 QuadriFlow 分部件输出也保留在任务目录中。

复用上述真实 ROCm GPU 分割，重新运行原生 QuadriFlow 和导出约 13 秒：
23 个部件、3,976 个四边面，移除 6 个零面积面、修复 20 个塌缩面，
实际 GLB 退化三角面从 66 降至 0，非流形边为 0。
双向表面采样距离 P95 约为包围盒对角线的 1.05%。

保留的 900 条开放边界不自动封口，以免封闭分割切口。
其中 294 条按输入边界的近似距离检查需复核；该标记不是精确的破洞分类。
界面显示质量摘要与开放边界提示，报告包含逐部件计数、距离阈值和位移记录。
最新证据是 `output/retopology-rocm-validation/verification.json`、
`geometry-validation.json`、`browser-validation.json` 和 `pipeline-browser.png`。
浏览器已验证旋转、部件切换、缩放，以及四种导出文件的下载 SHA256。

可复用保存的 GPU 分割重新验收：

```powershell
node dependencies/venv.cjs python scripts/repair_saved_retopology.py output/retopology-rocm-validation/preview-payloads.json --faces 5000
node dependencies/venv.cjs python scripts/inspect_retopology_result.py output/retopology-rocm-validation/preview-payloads.json
```
