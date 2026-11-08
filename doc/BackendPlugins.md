# Backend 插件与依赖注入

模型推理源码位于 `backend/plugins`；`extensions/*/ssui_*` 保留工作流节点、
参数控件和兼容导入。backend 不导入 SDK、server；已注册的插件之间不直接导入
对方实现，同一插件族内也遵循这一约束。内部未注册的辅助模块可以正常导入。
公共媒体对象由 `backend.contracts.media` 定义，SDK 重导出同一类型；服务端
将类型名映射回原来的 `ssui.base.*` / `ssui_image.*` 等名称，保持 UI 端口兼容。

## 装配与调用

`backend.application.create_application()` 是组合根，负责选择具体实现。
每个 executor 拥有一个应用和共享缓存，退出时释放资源。`SSLoader` 可显式接收
该应用；独立脚本调用 SDK 时使用适配器自己的应用。

业务代码通过函数参数或构造参数接收接口，不从注册表、全局单例或容器查找依赖。
插件发现与工厂执行不加载权重，也不导入 Torch/Diffusers；推理模块按需加载。
SDK 边界使用调用作用域关联工作流与应用，避免两个 loader 并发时互相覆盖提供者。
同一个模块能力的调用串行执行，保护线程不安全的上游管线。

目前显式注入的依赖包括：

| 使用方 | 接口 / 服务 | 默认实现 |
| --- | --- | --- |
| Qwen-Image 像素节点 | `PixelFinisher` | Image 像素后处理 |
| 像素后处理能力 | 注入的 Image 插件操作 | `image.PixelArt.finalize_pixel_art_image` |
| Motion 节点 | `PoseRecognizer`、`BlenderRenderer` | `motion.pose`、`motion.blender` |
| Blender 对比渲染 | `BVHExporter` | `motion.bvh` |
| SD1 / SDXL / FLUX 加载接口 | `ModelLoader` | 现有 ModelLoaderRegistry 和 ModelCache |
| FLUX.2 加载接口 | `DeviceService`、`ModelStore` | Torch 设备选择、应用级管线缓存 |
| H3 / LTX / Kimodo | `ProcessRunner`、`ExecutionContext` | 可取消子进程、逐次调用上下文 |

这些依赖均在插件的 `requires` 中声明，由组合根将提供者绑定为可调用接口。
例如 `motion.nodes → motion.blender → motion.bvh` 和
`video.QwenImage → image.pixel_finisher → image.PixelArt` 都属于装配图。
替换提供者后，消费方自动使用新提供者，不会绕过装配图导入默认实现。
跨插件共享的姿态选项等数据放在 `backend.contracts`，不从提供方实现模块获取。

`ExecutionContext` 保存本次调用的输出目录、种子、取消事件和进度回调。
目前旧模型节点仍保留原有配置参数；不会自动将上下文种子覆盖到模型参数上。
调用 backend 的进程能力时可显式传入上下文，SDK 默认创建独立上下文。
子进程与独立 Python 环境是两件事：默认子进程使用当前 Python，不要求另建 venv。

## 编写插件

公共协议放在 `backend/contracts`。例如需要图像后处理的插件工厂：

```python
from backend.plugins import Plugin
from backend.contracts.services import PixelFinisher

class AssetGenerator:
    def __init__(self, finisher: PixelFinisher):
        self.finisher = finisher

    def finish(self, image, **options):
        return self.finisher(image, **options)

def register(registry):
    def create(finisher):
        return {"assets.generator": AssetGenerator(finisher)}

    registry.register(Plugin(
        id="example.assets",
        provides=("assets.generator",),
        factory=create,
        requires={"finisher": "image.pixel_finisher"},
    ))
```

外部 Python 包声明 entry point，入口函数与内置插件使用同一注册协议：

```toml
[project.entry-points."ssui.backend_plugins"]
example-assets = "example_assets:register"
```

插件接口版本为 1。可选依赖用 `optional={参数名: 能力名}` 声明，缺失时注入
`None`；业务实现决定如何关闭增强能力。多个提供者必须用
`create_application(bindings={能力名: 插件ID})` 明确选择。
重复插件 ID、绑定歧义及循环依赖立即报错；缺少必需依赖或工厂失败仅使相关插件
不可用。资源按依赖顺序创建、逆序释放，可实现 `close()`。

测试可用 `services={"devices": fake_device_service}` 替换基础服务，或直接将 fake
对象传给实现。不要 mock 全局容器。兼容 SDK 保留旧测试 patch 位置，但新代码应
直接测试 backend 的注入接口。

## 安装与版本

共享基线为 Python 3.12、Torch 2.9.1 / TorchVision 0.24.1 / TorchAudio 2.9.1、
Transformers 5.1.0、Diffusers 0.42.1。Transformers 5 同时要求 Hub ≥1.3 和
Tokenizers 0.22–0.23，因此这些依赖一起升级。

`yarn update-lock:all` 按目标平台收集根依赖与共享扩展声明，再交给 uv 解析，
不使用 npm semver 合并 Python 约束。安装继续使用对应平台 lock。

| 锁文件目标 | Torch 发行栈 | 云端验证边界 |
| --- | --- | --- |
| windows / linux | CUDA 12.8 | 已解析；GPU 推理待本地验证 |
| windows-amdgpu | ROCm 7.2.1 官方 Windows wheel | 已解析；原生算子待本地验证 |
| linux-amdgpu | ROCm 6.4 Linux wheel | 已解析；GPU 推理待本地验证 |
| macosx | Apple Silicon / MPS | arm64 已解析；MPS 推理待本地验证 |

Linux 新 Torch wheel 需要 manylinux 2.28（glibc ≥2.28）。该组锁文件不承诺
macOS Intel 或 Linux ARM 的安装兼容性；这些架构需要独立验证的发行配置。

高级能力作为可选依赖安装，例如：

```bash
node dependencies/venv.cjs uv pip install -e ".[voice]" --build-constraint dependencies/build-constraints.txt
node dependencies/venv.cjs uv pip install -e ".[motion-generation]" --build-constraint dependencies/build-constraints.txt
node dependencies/venv.cjs uv pip install -e ".[h3-int8]" --build-constraint dependencies/build-constraints.txt
```

Kimodo 可选原生 motion_correction 编译可通过 `SKIP_MOTION_CORRECTION_IN_SETUP=1`
跳过；现有 Windows 安装脚本已改为安装到主环境。`SSUI_KIMODO_PYTHON`、
`SSUI_H3_PYTHON`、`SSUI_LTX_PYTHON` 仍可显式选择外部环境。

旧视频节点使用 backend 中的 DiffSynth 1.1.9 源码；H3 NF4 子进程使用已安装的
DiffSynth 2.2.0。精确包名 finder 代替全局 vendor 路径注入，避免其他顶层模块被
vendor 根目录意外遮蔽。DiffSynth 和 StdGEN 的 Transformers 5 导入变更已适配。

旧的 Torch 2.4/CUDA 12.4 原生 wheel 已从默认依赖移除。TRELLIS 等模型若需要
Kaolin、spconv、nvdiffrast、torch-scatter 或 Gaussian rasterization，必须安装
与本地 Torch/后端匹配的构建；没有兼容构建时该能力不可用，不能安装旧 wheel
绕过。Windows AMD 的 CuMesh/FlexGEMM/o-voxel 专用依赖仍按原平台声明保留。

## 检查与验收

```bash
yarn test
node dependencies/venv.cjs python -m backend.plugins
node dependencies/venv.cjs python -m backend.plugins --check-imports
```

默认检查只报告插件装配状态；`--check-imports` 进一步报告缺包和导入/API 错误，
不会下载权重，也不表示推理通过。未安装的可选能力会报告缺依赖。

云端验证包括五个平台锁文件解析、全量无权重测试，以及干净 CPU 环境安装和
`pip check` / 核心 API 导入。分发 wheel 应包含 runner、tokenizer 数据及 Blender
辅助资源。真实模型下载、量化、显存与原生算子仍需本地验收。

本地建议依次验证 SD/SDXL/FLUX、Wan/Qwen-Image、H3/LTX、Kimodo、CosyVoice、
TRELLIS/Pixal3D/StdGEN。每类至少完成一次加载、短推理及输出读取，检查取消后
子进程退出、再次运行可用，以及 CUDA/ROCm/MPS 没有退回 CPU。

回退时保留旧虚拟环境，并切回相应版本的源码和锁文件；不要在运行中的环境
直接混装两套 Torch 原生扩展。
