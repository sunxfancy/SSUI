# Windows ARM64 补充包发布

2026-10-29 的自建包已集中到
[ssui-python-packages](https://github.com/sunxfancy/ssui-python-packages/tree/main/arm64)。
原始 wheel SHA256、源码版本、补丁和发布验证记录由该仓库维护。
这批发布是已有二进制的校验迁移，本次没有重新执行完整源码构建。

## Python 3.12 CPU

`windows-arm64-cpu` 的 WeTextProcessing 已改用该仓库的固定版本；
原有 18 个自建包继续使用各自的固定版本。其他架构仍保留原来的来源。

## Python 3.13 CUDA

独立文件 `dependencies/requirements-windows-arm64-cuda-extensions.txt` 包含
11 个 GPU 包（CuMesh、FlexGEMM、NATTEN、nvdiffrast、o-voxel、cumm、spconv、
FlashAttention、PyTorch3D、torch-cluster、torch-scatter），以及 OpenCV 和
携带原生 ARM64 FreeType DLL 的 freetype-py。
每项固定版本和 SHA256；CUDA 与 CPU 包使用分离的索引。

只用于以下已验证组合：

- Windows ARM64、CPython 3.13；
- `torch==2.16.0.dev20261026+cu134`、CUDA 13.4；
- RTX Spark N1X，计算能力 12.1。

先准备官方 PyTorch 和所需普通运行依赖，再使用目标环境的 Python 安装：

```powershell
# 必须使用目标环境的 Python；下面路径替换为实际的 ARM64 CUDA 环境。
$armPython = 'C:/path/to/arm64-cuda-venv/Scripts/python.exe'
& $armPython -c "import sys,platform,torch; assert sys.platform=='win32' and platform.machine().lower()=='arm64'; assert sys.version_info[:2]==(3,13); assert torch.__version__=='2.16.0.dev20261026+cu134'; assert torch.version.cuda=='13.4'; assert torch.cuda.get_device_capability()==(12,1)"
if ($LASTEXITCODE -ne 0) { throw 'ARM64 CUDA runtime mismatch' }
& $armPython -m pip install --no-deps --only-binary=:all: -r dependencies/requirements-windows-arm64-cuda-extensions.txt
```

`--no-deps` 保留现有官方 PyTorch；这个文件是自建扩展清单，不是完整环境 lock，
也没有新增默认 CUDA runtime profile。不要装入 Python 3.12 CPU 环境。
FlexGEMM 首次执行 Triton 算子仍需 ARM64 MSVC 与 CUDA 工具链做 JIT 编译。

迁移后的实际 wheel 已在隔离安装目录通过 GPU 稀疏卷积参考对照、网格、光栅化、
注意力、体素、FPS/CSR、KNN/变换检查，以及 OpenCV 图像处理、FreeType 字形渲染。
CPU WeTextProcessing 已通过中文归一化检查。算子通过不代表所有训练路径或模型
都已验证；完整报告随各自 Release 发布。
