# 自动骨骼绑定：UniRig / MIA / RigAnything

SSUI 新增 `AutoRigMesh` 节点，输入 `Mesh`，选择模型后输出带骨架和蒙皮的原始
GLB。示例：`examples/advance/workflow-auto-rig.py`。参数准备阶段不加载权重，
实际推理在各模型的独立 Python 子进程执行。

## 当前验证状态

- 三个官方源码版本已固定于 `rigging_models.json`，包含 MIA 的子模块。
- 接入官方推理阶段，提供安装入口、工作流、日志和真实模型冒烟命令。
- 自动验证 GLB 包含被 mesh node 引用的 skin、有效关节索引、JOINTS_0 和 WEIGHTS_0。
- SSUI 执行器直接复制路径型 `Mesh` 的 GLB，避免 trimesh 重新导出时丢失蒙皮。
- Windows ARM64 已新增现代 CUDA 安装路径：Python 3.13、NVIDIA
  `torch 2.16.0.dev20261026+cu134`、CUDA Toolkit 13.4、MSVC ARM64、Blender bpy 5.2.3。
  RTX Spark N1X 的实际计算能力为 12.1，自编译 CUDA 扩展已执行通过。
- **RigAnything 已完成真实 GPU 推理和蒙皮变形验证**：官方 Spyro 示例生成 34 个
  关节，约 72 秒；旋转有权重的非根骨骼后，2,697 / 5,211 个顶点发生位移。
  本机结果：`output/rigging/riganything_lv64y6tm/rigged.glb`。
  另将输入转换成不含 skin 的静态网格后重新绑定，约 45 秒生成 32 个关节，
  2,948 / 5,213 个顶点在骨骼旋转后发生位移；结果位于
  `output/rigging/riganything_f6q0p36i/rigged.glb`。
- torch-cluster 1.6.3、torch-scatter 2.1.2、PyTorch3D 0.7.9、FlashAttention 2.8.3
  已构建 ARM64 CUDA wheel；FPS、CSR 归约、原生 KNN、变换和 FlashAttention 前向
  已对照 PyTorch 参考结果通过。cumm 0.7.11、spconv 2.3.8 的 ARM64 CUDA wheel
  也已生成，真实稀疏卷积与 dense CPU 参考对照通过。
- **UniRig 已完成骨架、蒙皮、合并 GLB 和变形验证**：官方长颈鹿示例生成 43 个
  关节，约 147 秒；旋转加权骨骼后 6,038 / 14,932 个顶点发生位移。
  结果：`output/rigging/unirig_zedzmo7d/rigged.glb`。
- 补充从 FreeType 2.13.3 官方源码编译 ARM64 DLL，安装到 UniRig 的 freetype-py
  包目录，解决 pyrender 字体库加载。GL 离屏深度测试按 UniRig 使用的深度还原
  公式验证，未修改参考模型的体素化算法。
- MIA 公开权重已下载，受限 `jasongzy/Mixamo` 骨架模板下载需要本机 Hugging Face
  登录及数据集访问权限。只有完成模板下载和真实模型验证后才能确认 MIA 可用。

## 安装

在仓库根目录执行：

```bash
# 任意平台：只下载三个固定版本的源码，不下载权重，不改变 SSUI 共享依赖
yarn install:rigging all --source-only

# 本机 Windows ARM64：复用已验证的 NVIDIA CUDA Python，模型依赖安装在独立 venv
yarn install:rigging riganything --cuda-native --base-python .build/cuda-arm64-venv/Scripts/python.exe --download
yarn install:rigging mia --cuda-native --base-python .build/cuda-arm64-venv/Scripts/python.exe --download
yarn install:rigging unirig --cuda-native --base-python .build/cuda-arm64-venv/Scripts/python.exe --download

# 在兼容 CUDA 的环境，使用实际的 Python 3.11 路径
yarn install:rigging unirig --python /path/to/python3.11 --download
yarn install:rigging mia --python /path/to/python3.11 --download
yarn install:rigging riganything --python /path/to/python3.11 --download
```

默认源码目录：`models/rigging/<模型名>`；默认隔离环境：`.venv/rigging/<模型名>`。
不把三个模型的依赖加入 SSUI 共享 venv。安装器遇到有已跟踪文件改动的源码目录
会停止，保留本地修改。

原生依赖仍需按照所选 PyTorch/CUDA/操作系统配置；安装脚本不是跨平台移植：

| 模型 | 上游运行要求 / 注意事项 |
| --- | --- |
| UniRig | CUDA；requirements 含 FlashAttention、bpy 4.2；另需匹配的 spconv、torch_scatter、torch_cluster。先按官方说明完成原生依赖。 |
| MIA | 当前固定 main 版本（v1），不是 v2；上游固定 Torch 2.1.2/cu121、PyTorch3D 和 bpy 4.3，较新 GPU 可能需要另行移植依赖。需要 `data/Mixamo/bones*.fbx` 模板和 `output/best/new/` 权重。 |
| RigAnything | CUDA（上游硬编码 cuda:0）；bpy、open3d、pymeshlab；权重放在 `ckpt/riganything_ckpt.pt`。 |

上述表格记录上游旧依赖组合。`--cuda-native` 使用新版 ARM64 CUDA 栈：
RigAnything 的 GLB 简化直接用 Blender 完成，不加载只供 OBJ 分支使用的
Open3D/PyMeshLab；MIA 改用 Gradio 6 和兼容的 Transformers 5.1，避免安装推理不需
使用的 TensorBoard。独立环境通过 `.pth` 读取 CUDA base 的包，新增依赖只写入
模型自己的环境，不修改 base。应保留 `--base-python` 对应的环境。

Windows ARM64、Python 3.13、CUDA 13.4 / PyTorch `2.16.0.dev20261026+cu134`
已有发布的原生扩展和 FreeType 包，可按
[ARM64 包安装说明](../../doc/WindowsArm64Packages.md)安装固定版本与 SHA256 的 wheel。
这些包只适用于文档中的 ABI 和 GPU 架构组合。

需要从源码重建时，使用以下命令（先读取根 `package.json`）：

```bash
yarn build:rigging:cuda
yarn build:rigging:cuda --package torch-cluster
yarn build:rigging:cuda --package torch-scatter
yarn build:rigging:cuda --package pytorch3d
yarn build:rigging:cuda --package flash-attn
yarn build:rigging:cuda --package cumm --python .venv/rigging/unirig/Scripts/python.exe
yarn build:rigging:cuda --package spconv --python .venv/rigging/unirig/Scripts/python.exe
yarn build:rigging:cuda --package freetype --python .venv/rigging/unirig/Scripts/python.exe

# 复用本机构建的 wheel，例如安装 MIA 需要的 FPS 与几何库
yarn build:rigging:cuda --package torch-cluster --reuse --python .venv/rigging/mia/Scripts/python.exe
yarn build:rigging:cuda --package pytorch3d --reuse --python .venv/rigging/mia/Scripts/python.exe

# GPU 算子对照验证；缺失组件会失败，不会静默跳过
yarn test:rigging:cuda --python .venv/rigging/riganything/Scripts/python.exe --ops pyg pytorch3d flash-attn
```

构建脚本自动加载 ARM64 MSVC，使用 C++20 和计算能力 12.1。
`build_hooks/sitecustomize.py` 只在构建子进程启用：修复 Windows 编译输出编码、
旧 PyG 关闭 Ninja 导致 `.cu` 被交给 cl 的问题，以及中断代码生成后的缓存恢复。
CUDA 13 的模板符号可见性通过 NVCC 选项处理。cumm 增加 Blackwell 架构识别及
ARM64 CUDA 库目录；FlashAttention 构建只初始化 CUDA 所需 Cutlass 子模块。
构建源码在 `.build/rgsrc/`，wheel 在 `.build/rigging-cuda/wheels/`，
算子验证报告在 `.build/rigging-cuda/`。
当前完整环境和检查结果见 `doc/windows-arm64-rigging.json`。缓存的 wheel 仅供相同
Python / PyTorch / CUDA ABI 的环境复用。FreeType DLL 和许可证缓存在
`.build/rigging-cuda/freetype/`，它是 CPU 字体库；模型计算和原生算子使用 CUDA。

UniRig / RigAnything 默认安装 cu128 PyTorch，可用 `--torch-index-url` 指定匹配的
官方 wheel 索引。UniRig 的 PyG/spconv 版本应与实际 Torch/CUDA 一起选择，安装命令见
[官方安装说明](https://github.com/VAST-AI-Research/UniRig#installation)。
MIA 保留官方 requirements 的旧版本组合，不自动升级以免静默改变结果。
权重使用上游发布位置；源码固定不代表 Hugging Face 权重已固定哈希。

如果已手工配置环境，可使用环境变量覆盖绝对路径：

```text
SSUI_UNIRIG_REPO / SSUI_UNIRIG_PYTHON
SSUI_MIA_REPO / SSUI_MIA_PYTHON
SSUI_RIGANYTHING_REPO / SSUI_RIGANYTHING_PYTHON
```

这些变量指向运行 SSUI 的同一台主机上的目录和解释器，当前适配器不提供远程调用。
在 Linux CUDA 主机上运行 SSUI 执行器即可使用其本地模型环境。

## 工作流与验证

打开 `examples/advance/workflow-auto-rig.py` 的 `auto_rig` 工作流并上传网格。
选择 `unirig`、`mia` 或 `riganything`。也可在 SDK 中显式指定环境：

```python
from ssui import Mesh
from ssui_3dmodel.AutoRig import AutoRigModel

result = AutoRigModel.load_local("unirig").rig(Mesh.load("character.glb"))
print(result.path)  # 原始、带骨架的 GLB，供下载或 Blender 使用
```

```bash
# 无权重回归：参数准备、沙盒发现、失败处理、GLB skin 检查、导出原始字节保留
yarn test:rigging

# 真实推理，失败时返回非零退出码；必须预先安装相应环境和权重
yarn test:rigging:smoke unirig --input input/character.glb
yarn test:rigging:smoke mia --input input/character.glb
yarn test:rigging:smoke riganything --input input/character.glb
# 同时检查实际骨骼驱动变形
yarn test:rigging:smoke riganything --input input/character.glb --verify-deformation
```

每次运行创建独立 `output/rigging/<模型名>_<唯一值>/`，保存输入、推理日志、
阶段产物和 `rigged.glb`。冒烟成功后才写出关节数、耗时和输出路径报告。
模型返回静态 GLB、无蒙皮或无输出时均报错，不使用传统绑定算法代替模型推理。

`target_faces` 控制 UniRig 的预处理及 RigAnything 的简化目标；MIA 保持官方
表面采样流程，该参数不影响 MIA。`seed` 用于 UniRig 和 MIA；RigAnything 当前
上游固定种子为 777，节点传入的种子不改变它。MIA 使用推理后的 Blender 场景
直接导出 GLB，同时保留 FBX，不依赖 Linux 专用的外部 FBX2glTF 工具。

RigAnything 上游固定的是 Torch 种子；表面采样仍可能变化，不能据此保证完整流程
逐次产生相同关节数。UniRig 合并阶段使用官方合并实现，移除其未使用的 Open3D
导入；包装器若检测到该模块实际引用 Open3D 会停止，不会伪造该依赖。
UniRig 的旧 skin checkpoint 以 Box 保存配置元数据；推理包装器将该元数据解码为
OrderedDict，保留 `weights_only` 加载。每次推理使用独立临时目录和 UTF-8 日志，
避免 Windows 临时目录权限和 GBK 编码导致模型运行中断。

本次验证覆盖骨架、蒙皮和几何变形。Blender 导出曾报告多个纹理采样器和顶点颜色
相关警告，尚未对所有材质做逐像素一致性验证。

路径型 `Mesh` 是不可变产物，`_model` 可以为空；需要几何处理时显式通过
`Mesh.load(result.path)` 读取，但几何处理后重新导出不保证保留绑定数据。
自动绑定只生成骨架和蒙皮，不包含动作生成、控制器或动画重定向。
生产使用前仍需在 Blender 检查关节位置、弯曲变形和模型/权重许可。

官方项目：[UniRig](https://github.com/VAST-AI-Research/UniRig)、
[MIA](https://github.com/jasongzy/Make-It-Animatable)、
[RigAnything](https://github.com/Isabella98Liu/RigAnything)。
