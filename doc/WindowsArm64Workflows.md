# Windows ARM64 CPU 启动与真实模型验收

日期：2026-10-24。使用 Windows ARM64 CPython 3.12.15，安装
`dependencies/windows-arm64-cpu.lock` 的 249 个包，PyTorch 2.9.1+cpu。

## 已验证的链路

使用真实 FastAPI 服务、WebSocket 调度器和独立原生执行器，经
`/api/script`、`/api/prepare`、`/api/execute` 执行工作流，没有替换模型或模拟推理。

| 工作流 | 模型与输入 | 验证结果 |
| --- | --- | --- |
| `examples/basic/workflow-sd1.py` / `txt2img` | 完整 SD1.5 checkpoint，CPU FP32；512×512，DDIM 4 步，CFG 7.5，seed 42 | 提示词编码、UNet 去噪、VAE 解码、PNG 保存与任务结果回传通过；输出为森林中的狐狸，非空白图 |
| `examples/basic/workflow-chat.py` / `chat` | Qwen2.5-0.5B-Instruct，CPU；temperature 0，max_length 128 | 返回 `The capital of France is Paris.`，历史记录与生成文本一致 |
| `examples/advance/workflow-pose.py` / `video_to_skeleton` | 官方 MediaPipe pose lite 模型；由官方 pose.jpg 编码的 1 秒、5 fps 视频 | 输出 5 帧姿态、预览 MP4、骨骼 JSON、BVH 与 retarget JSON，retarget RMSE 约 0.01277 |

SD1.5 是真实完整权重，4 步用于检查完整推理链路，不代表生产画质或性能基准。
姿态视频由同一张正样本重复编码，验证视频输入、时间戳、推理和输出链路，不代表运动追踪精度验收。

模型固定版本及校验值见 `windows-arm64-cpu-model-sources.json`。
三项工作流的验收结果见 [JSON 报告](windows-arm64-cpu-workflows.json)。
服务端点、静态资源与原生桌面构建结果见 [启动报告](windows-arm64-cpu-startup.json)。
其中 SD1.5 还经过 Edge 的模型选择、参数设置及运行按钮提交，HTTP 返回 200；
输出文件通过 HTTP 获取并校验像素与 SHA256，与此前 API 生成的文件完全一致。
浏览器连接在推理期间断开，因此没有把最终页面预览或截图标记为通过。
模型与生成文件保留在本地 `.build/arm64-models`、`examples/*/output`，不会提交大型权重。

## 本轮修复

- Uvicorn 开发启动改用应用导入字符串，避免 `--dev` 直接退出；排除本地构建、虚拟环境、Node 依赖与 Git 缓存目录。
- 执行器将同步模型加载、推理和结果文件保存移到工作线程，保持 asyncio 事件循环响应，避免 CPU 长任务阻塞 WebSocket 心跳。每个执行器仍串行处理任务。
- 调度器兼容 IPv4 与 IPv6 的远端地址元组。
- 工作流函数发现使用解析后的类型注解，修复 RestrictedPython 产生字符串注解时页面出现“没有可运行函数”的问题；覆盖模型参数、列表与多个返回值。
- 新版 Qwen 使用公开的 chat template / generate 接口，保留旧版模型 `.chat()` 路径及历史记录约定。
- 无 HTTP 路由的 SDK 扩展正常加载；修复示例扩展未定义路由器的问题。
- 当 OpenCV 没有视频编码后端时，姿态预览通过随包 FFmpeg 编码。
- Windows ARM64 的 WASM 构建跳过 wasm-pack 不支持下载的 `wasm-opt`，保留 Rust release 优化；其他主机保持原构建步骤。

## 可复现验收

先按 [依赖记录](WindowsArm64Dependencies.md) 安装原生 ARM64 环境。
为避免修改其他开发环境，显式设置该虚拟环境；模型下载需要联网，实际推理使用本地模型。
首次 checkpoint 转换仍可能获取上游配置/tokenizer；离线运行需保留对应缓存。

```powershell
$env:SSUI_VENV_PATH = "$PWD\.build\arm64-integration-venv"

# 两个终端分别启动服务与执行器
yarn dev:server
yarn dev:executor

# 在原生 ARM64 Python 下运行，显式选择真实模型验收项目
yarn test:arm64-workflows --server http://localhost:7422 `
  --check sd1 --check qwen --check pose `
  --sd1-model .build/arm64-models/sd1/v1-5-pruned-emaonly.safetensors `
  --qwen-model .build/arm64-models/qwen `
  --pose-video .build/arm64-remaining/pose-input.mp4 `
  --pose-model .build/arm64-probe-assets/pose_landmarker_lite.task `
  --output .build/arm64-remaining/workflows.json
```

`test:arm64-workflows` 不下载权重：它检查 CPU 服务、函数发现、prepare、execute、
图像尺寸与像素变化、非空文本及历史、视频/BVH/骨骼文件的 HTTP 获取。
需要已有的官方模型与测试输入；缺少输入时直接报错，不会用假模型替代。

固定下载版本：

```powershell
node dependencies/venv.cjs python -c "from huggingface_hub import hf_hub_download; hf_hub_download('stable-diffusion-v1-5/stable-diffusion-v1-5', 'v1-5-pruned-emaonly.safetensors', revision='451f4fe16113bff5a5d2269ed5ad43b0592e9a14', local_dir='.build/arm64-models/sd1')"
node dependencies/venv.cjs python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-0.5B-Instruct', revision='7ae557604adf67be50417f59c2c2f167def9a775', local_dir='.build/arm64-models/qwen', allow_patterns=['*.json','*.safetensors','*.txt'])"
yarn probe:arm64 --check mediapipe-ssui --download-assets --assets-root .build/arm64-probe-assets --output .build/arm64-remaining/mediapipe.json
```

姿态测试输入由 `arm64-probe-assets/pose.jpg` 经 FFmpeg 编码，缩放到宽 512、
保持偶数高度、5 fps、1 秒、H.264/yuv420p。输入图与 `.task` 的 SHA256 在
`dependencies/arm64-probe-assets.json` 中固定。

## 验证范围

- 默认 Python 回归：132 项，120 项通过、12 项按配置跳过。
- `uv pip check` 对全部 249 个已安装包通过；本轮应用修复没有新增 Python 依赖，原 lock 保持有效。
- 共享组件、Functional UI、Image 编辑器的 TypeScript/Vite 构建及 WASM release 构建通过。
- 原生 `aarch64-pc-windows-msvc` Tauri debug 构建通过，PE machine 为 `0xaa64`。首次构建需 MSVC ARM64 与 PATH 中的 clang；本轮补齐工具链后成功。Cargo.lock 同步了自身包的既有 0.2.0 版本，没有升级 Rust 依赖。
- 项目自带 `scripts/smoke_app.cjs` 的原生桌面启动检查通过，进程保持运行 20 秒。安装器和完整桌面交互尚未验收。
- 以上三项真实模型工作流不替代所有模型的回归。SDXL、Flux、CosyVoice、3D 模型和 GPU 后端尚未完成本轮真实权重验收。
- Canvas 的实际 WebGPU 绘制、OpenGL 渲染、桌面安装器与自动更新不在上述模型检查覆盖范围内。
- 保持 Windows ARM64 CPU profile 的实验支持标记。

原生桌面构建命令（在包含 clang 的 ARM64 MSVC 开发环境中）：

```powershell
yarn build:desktop:debug --no-bundle --target aarch64-pc-windows-msvc
node scripts/smoke_app.cjs desktop/src-tauri/target/aarch64-pc-windows-msvc/debug/ssui.exe 20
```

进程启动冒烟仅检查缺少 DLL 或立即崩溃等问题，不替代安装器、桌面内各项交互及所有模型验收。

本轮临时验证服务已关闭，浏览器测试使用的临时模型登记已移除；权重和生成文件保留，可通过上述命令复现。
