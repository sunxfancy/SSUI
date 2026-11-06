# Linux 安装与验收

本次实测平台为 Linux x86_64 / NVIDIA RTX 3090 24 GB。AMD、ARM64 和其他发行版不在此次 GPU 验收范围内。

## 源码安装

准备 Node.js、Yarn Classic、Git、curl。桌面构建还需要 Rust 和 Tauri 系统开发库。
Ubuntu/Debian 的开发库包括 `build-essential`、`pkg-config`、`libwebkit2gtk-4.1-dev`、
`libayatana-appindicator3-dev`、`librsvg2-dev`、`patchelf`、`libssl-dev` 和 `libxdo-dev`。
仅安装 appindicator 运行库不够：Tauri 打包还需要开发包提供的 pkg-config 文件。

```bash
yarn install --frozen-lockfile
yarn doctor:native
yarn dev:desktop
```

默认安装流程先安装 `linux.lock`，再在可用的 Linux x86_64 NVIDIA CUDA 环境上准备原生扩展。
工具链通常存放在安装目录 `.venv/native-cuda/`，不修改系统 CUDA 或 GCC。
安装路径含空白时，通过用户私有缓存中的稳定路径别名启动 Python，并把原生编译工具和临时源码放在无空白的缓存路径，规避 Torch 2.4 的编译/链接命令限制；项目和权重不移动。
原生包面向 Python 3.12 / Torch 2.4.1+cu124，包括 nvdiffrast 0.3.3、Kaolin 0.17.0、
spconv-cu124 2.3.8、bitsandbytes 0.45.5 和固定提交的 Gaussian rasterizer。
同一安装步骤包含 MDM 所需的兼容 Python 依赖，权重和人体模型资产仍需单独准备。
编译器使用精确锁 `dependencies/native-cuda-linux.explicit.txt`，无需再次求解 Conda 依赖。

```bash
# 修复或单独安装原生栈；要求实际可用的 NVIDIA CUDA。
yarn install:native
yarn doctor:native

# CPU/无 NVIDIA 环境可以仅安装基础依赖。
SSUI_SKIP_NATIVE_CUDA=1 yarn install-requirements
```

`dependencies/venv.cjs` 和桌面 Rust 启动器共用 `dependencies/native_cuda.py`。
完成原生安装后，正常的 server/executor 启动入口自动获得同一 CUDA_HOME、编译器、头文件和 Torch 扩展缓存，
无需手工执行 micromamba 激活脚本。启动时不会下载安装依赖。
升级工具链在新目录完成编译和 GPU 前向/反向检查后才原子切换；失败不会撤销已有可用运行环境。

模型权重不包含在安装包里，仍需按模型许可单独准备。TRELLIS 的本地 DINOv2 源码/权重入口和
各模型实测命令见 [ModelValidation.md](ModelValidation.md)。MDM 额外资产见 [Motion README](../extensions/Motion/README.md)。

## Linux 桌面包

```bash
yarn package:linux
yarn test:package-resources
```

默认扩展归档包括 Image、Video、Audio、3D-Model、Motion；Video/3D 归档必须包含 SDK 和 vendor 源码。
安装器给 Linux 使用 `linux.lock`，通过独立 Python 创建 `.venv`，安装包解压后即可从桌面选择示例工作流。
默认生成 AppImage；添加执行权限后直接运行。Git 仍需通过系统包管理器准备。AppImage 开启媒体框架打包；构建机需安装 GStreamer base/good/libav 插件，以将 H.264 播放依赖带入安装包。
桌面在线安装使用与源码相同的 UV 版本、依赖锁和隔离构建约束。
离线基础包安装保持离线行为，不会隐式联网准备 CUDA 工具链；原生扩展需要预装或另行在线准备。

## 回归

```bash
yarn test
yarn test:install
# 会实际下载 Python 并从空目录引导，路径包含空格。
SSUI_RUN_INSTALL_TESTS=1 yarn test:install
yarn test:package-resources
yarn test:desktop:rust --release python::tests
```

GPU 可用性以 CUDA 实际运算为准；PCI 设备存在或 torch 能导入不代表 CUDA 已可用。
完整桌面交互与模型质量验收必须另行记录，不能用默认单元测试或程序存活代替。

真实桌面自动化入口是 `yarn test:desktop:linux`，需要 `tauri-driver`、WebKitWebDriver、Xvfb 和 dbus-run-session。
可通过 `SSUI_TAURI_DRIVER` / `SSUI_WEBKIT_DRIVER` 指定工具路径。测试解压实际 AppImage，在隔离配置目录中
通过真实安装向导创建环境、自动启动后端，并从工作流选择器复制视频和 3D 示例；测试产物保留在 `.build/desktop-linux-smoke/`。
默认不调用这些有网络和 GPU 开销的测试。

## 2026-11-01 与 dev 0.3.0 合并

保留统一的 OS/架构运行时配置、共享开发环境、新动作协议及现有模型加载器。
这里增加的 MDM 示例为 `workflow-mdm.py`，原 `workflow-motion.py` 继续使用 Kimodo。
Wan 的 GPU 常驻版本放在 `ssui_video.Wan21Resident`，与现有跨平台 `Wan21` 入口共存。
GLBPreview 是附加输出页签，现有部件预览、质量报告与导出入口保留。
自定义 `SSUI_VENV_PATH` 的共享环境不自动安装本地 `.venv` 的原生栈。

历史 GPU 推理和 Debian 原生桌面记录基于合并前环境，不能等同于当前 dev 依赖版本全部通过 GPU 验收。
合并后已重新检查 Python 回归、前端构建及组件/功能 UI/桌面测试，结果见 PR 描述。

## 2026-11-06 AppImage 运行时修复

真实测试改为启动 AppRun，覆盖用户实际获得的环境。修复 AppRun 的 PYTHONHOME 污染独立 Python、安装资源缺失 flow_compiler.py、未打包 GStreamer 媒体框架，以及执行器扩展导入优先级。
当前 AppImage 已在升级后的独立 GUI 环境中完成 GPU 后端、H.264 与 GLB 预览、错误反馈和真实 Wan 推理播放验证。
复验命令为 `SSUI_WAN_MODEL_DIR=<本地权重目录> yarn test:desktop:linux`；保留 `SSUI_SMOKE_ARTIFACT` 时重放已有安装环境，不设置时执行全新安装。
不要通过外部 GST_PLUGIN_PATH 来替代安装包媒体依赖验收。

Linux 在线首次安装使用运行时注册表固定的 UV 版本和源码安装入口相同的构建约束。
扩展资源目录中的 Readme.md 等非归档文件不再传给解压器，避免安装最后一步失败。
自动化验收会将实际 Torch/Diffusers/Transformers 版本与包内 Linux 锁对照，并检查真实 Wan 播放进度、保留 `wan-result.png` 截图。
