# Windows ARM64 CPU 依赖接入与审计

检查日期：2026-10-24。目标：Windows ARM64、CPython 3.12.15、CPU。

依赖源为 `dependencies/dependencies.yaml` 的 `windows / arm64 / cpu` override。
本轮只更新该 profile 的生成 requirements、lock 和依赖关系 YAML，保留其他平台配置。

## 接入结果

- 最终 lock 共 **249 个包**，以 `aarch64-pc-windows-msvc`、Python 3.12.15 和 `--no-build` 解析成功。
- 在独立原生 ARM64 虚拟环境中实际安装并同步整份 lock；`uv pip check` 通过。
- [wheel 审计](windows-arm64-cpu-wheel-audit.json)覆盖全部 249 个包，均找到兼容 wheel（包含一个直接 URL wheel）。
- [运行探针](windows-arm64-cpu-runtime-probe.json)的 **24 项检查全部通过**，包括 CPU 张量、torchvision NMS、torchaudio 重采样、Numba JIT、ONNX Runtime CPU 推理、OpenCV 图像处理、Arrow Snappy Parquet、PyVista/PyMeshFix 网格修复、Pynini/WeTextProcessing、Hydra/ANTLR、librosa、SoundFile WAV 读写、Whisper 文件解码、Motion 视频输入、MediaPipe 人脸与姿态、ControlNet 人脸检测及流式生成。
- 配置与目标选择测试共 21 项、wheel 审计单测 4 项、原生工具配置单测 3 项通过；所有生成 requirements 一致性检查通过。

已进一步启动真实服务与执行器，完成 SD1.5 文生图、Qwen2.5 对话、MediaPipe 姿态工作流；详见[启动与模型验收](WindowsArm64Workflows.md)。其他模型、OpenGL 渲染或 ARM64 桌面安装包仍需单独验收。
profile 仍标记为实验支持。

## 自建 wheel 来源

所有自建包固定到已发布的完整 `+ssui...` 版本，索引中的下载链接带 SHA256。
不使用浮动的“最新构建”，不执行源码构建，不接受改名的 x64 wheel。

| 包 | 固定版本 |
| --- | --- |
| Pynini | `2.1.6.post1+ssui.cpu.r1.b9c91f73d4a44` |
| opencv-python-headless | `4.11.0.86+ssui.cpu.r1.b05e8c6d74ea4` |
| pyarrow | `20.0.0+ssui.cpu.r1.b9bfc03949403` |
| VTK | `9.4.2+ssui.cpu.r1.b62943278488d` |
| pymeshfix | `0.17.1+ssui.cpu.r1.b9816cfcfdc6b` |
| torchaudio | `2.9.1+ssui.cpu.291.r1.ba7c51896a4b0` |
| pyworld | `0.3.4+ssui.cpu.r1.b83bf5208b453` |
| soxr | `0.5.0.post1+ssui.cpu.r1.b9f0b72cc0d95` |
| tiktoken | `0.9.0+ssui.cpu.r1.bb0e785dac3f7` |
| glcontext | `3.0.0+ssui.cpu.r1.bf1816f253e6a` |
| moderngl | `5.12.0+ssui.cpu.r1.be987004179e0` |
| hf-transfer | `0.1.9+ssui.cpu.r1.b0a21e114de54` |
| antlr4-python3-runtime | `4.9.3+ssui.cpu.r1.b0faf253a9595` |
| openai-whisper | `20240930+ssui.cpu.r1.b7b7485ae8627` |
| imageio-ffmpeg | `0.6.0+ssui.cpu.r2.b06fa0f77c82a` |
| mediapipe | `1.1.1+ssui.cpu.r1.b45e54946cee2` |
| transformers-stream-generator | `0.0.4+ssui.cpu.r2.b410865ecf176` |
| controlnet-aux | `0.0.10+ssui.cpu.r1.b7286b30fa4bc` |

CPU 包索引：<https://sunxfancy.github.io/ssui-python-packages/simple/windows/arm64/cpu/>。
torchaudio 使用单独的 `cpu/2.9.1/` 通道，并与官方 torch `2.9.1+cpu` 配对。
PyVista 固定 `0.46.3`，与本轮验证的 VTK `9.4.2` 配对。

OpenCV 的两个发行包都会安装 `cv2`。当前选择 headless，恢复 controlnet-aux 和 rembg；
**已发布的 opencv-contrib-python 不同时装入此环境**；MediaPipe 补充 wheel 统一依赖该 headless 版本，保留官方 ARM64 原生 DLL。
OpenCV 不带 FFmpeg、Media Foundation 和可选 FP16 CPU dispatch；Arrow 不含 S3/GCS/Flight；
VTK 不含 Qt/MFC。相关构建证据见[合集仓库构建记录](https://github.com/sunxfancy/ssui-python-packages/blob/main/docs/arm64-build-results-2026-10-23.md)。

## 本轮进一步解决的问题

| 问题 | 调整及验证 |
| --- | --- |
| 旧版本 Numba/llvmlite 缺少 ARM64 wheel | 改用官方 [Numba 0.68.0](https://pypi.org/project/numba/0.68.0/) 与 [llvmlite 0.50.0](https://pypi.org/project/llvmlite/0.50.0/)；实际 JIT 编译执行通过，目标 triple 为 aarch64，恢复 librosa、Whisper 和 rembg 的依赖链 |
| SoundFile 0.12.1 通用 wheel 缺少 libsndfile.dll | ARM64 profile 升到官方 SoundFile 0.14.0 原生 wheel；WAV 读写及 librosa 重采样通过 |
| pyworld 导入 pkg_resources 失败 | ARM64 profile 固定 setuptools 80.9.0；音高计算通过，避免 setuptools 81+ 移除该模块造成运行失败 |
| 直接 URL 包未出现在依赖关系 YAML | 修正 lock 图解析，保留 WeTextProcessing 的版本、URL、根依赖与反向依赖；添加回归测试 |
| rembg 首次导入超过初版探针的 180 秒限制 | 首次 Numba 编译较慢；将可配置的单项超时设为 300 秒，复测和最终整套检查均通过 |

旧审计针对的 Numba 0.62.1 / llvmlite 0.45.1 组合，不能代表本轮新版官方组合。
合集仓库中的旧版本移植 recipe 仍禁用，SSUI 直接使用上述新版官方 wheel。
初始历史审计保留在 [initial audit](windows-arm64-cpu-initial-audit.json)，不代表当前 lock。

## 本轮解除的三个阻塞

| 组件 | 当前结论 |
| --- | --- |
| imageio-ffmpeg / FFmpeg 文件输入输出 | 合集统一构建并发布 ARM64 FFmpeg 9.0.2、x264 和 imageio 包装器；恢复 ffmpeg extra。SSUI 自动配置随包二进制，验证 H.264 编解码、ffprobe、Motion 视频读取和 Whisper WAV 文件解码 |
| mediapipe | 统一 cv2 提供者；将 SSUI 人脸入口及 controlnet-aux 适配到 Tasks API，保留旧版本 Solutions 分支。正样本验证人脸、姿态及视频时间戳，空白图验证无检测结果 |
| transformers-stream-generator | 使用公开 generation/streamer API，固定 Transformers 4.57.6、tokenizers 0.22.2。验证批量贪心、固定种子采样与普通生成一致，以及普通 beam、异常传播和提前取消 |

当前 lock 没有未解决的发行包、标签或依赖解析阻塞。四个补充包均已通过合集 CI 独立发布；源码、指纹、许可证与测试说明见[本轮发布记录](https://github.com/sunxfancy/ssui-python-packages/blob/main/docs/arm64-compatibility-2026-10-24.md)。

仍有能力边界：FFmpeg 使用 CPU 构建，启用 GPL x264，未启用硬件加速及其他外部编解码库；流式 beam search 明确不支持，普通 beam search 已验证。其他大模型工作流、GPU 后端和 OpenGL 渲染仍需单独验收，profile 保持实验支持。

## 复现

```powershell
$env:SSUI_UV_PATH = 'C:\path\to\uv.exe' # 使用已支持 ARM64 triple 的 uv 0.13.5

yarn requirements:generate --target windows-arm64-cpu
yarn update-lock:no-upgrade --target windows-arm64-cpu

# 指向独立原生 ARM64 虚拟环境，不修改既有开发环境
$env:SSUI_VENV_PATH = 'C:\path\to\arm64-venv'
& $env:SSUI_UV_PATH pip sync --python "$env:SSUI_VENV_PATH\Scripts\python.exe" `
  dependencies/windows-arm64-cpu.lock --only-binary :all: --index-strategy unsafe-best-match
& $env:SSUI_UV_PATH pip check --python "$env:SSUI_VENV_PATH\Scripts\python.exe"
yarn probe:arm64 --download-assets --assets-root .build/arm64-probe-assets `
  --output doc/windows-arm64-cpu-runtime-probe.json

# 审计全部锁定包，不下载 wheel、不执行包构建代码
yarn audit:wheels dependencies/windows-arm64-cpu.lock --python-version 3.12.15 `
  --extra-index-url https://download.pytorch.org/whl/cpu `
  --extra-index-url https://sunxfancy.github.io/ssui-python-packages/simple/windows/arm64/cpu/ `
  --extra-index-url https://sunxfancy.github.io/ssui-python-packages/simple/windows/arm64/cpu/2.9.1/ `
  --output doc/windows-arm64-cpu-wheel-audit.json

yarn test:runtime-target
yarn test:dependency-config
yarn test:wheel-audit
yarn test:native-tools
yarn requirements:check
```
