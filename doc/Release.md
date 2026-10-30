# SSUI 桌面发布

本阶段仅 Windows、macOS、Linux × x86_64、ARM64，共六个目标。
不包含 Android、iOS、32 位或任意主机间的交叉编译承诺。

## 流程

1. 在 `dev` 上通过 PR 准备版本、变更说明和兼容性说明。同步
   `desktop/src-tauri/Cargo.toml`、`desktop/package.json` 和 Cargo.lock 中
   ssui 自身的版本；运行 `python scripts/release.py check-versions`。
2. 合入版本 PR 后，针对该确定提交创建 `vX.Y.Z` GitHub Pre-release。
   tag 必须已包含正确版本，不再由 CI 移动。禁止重用或覆盖旧 tag。
3. `Release` 校验版本，记录提交 SHA，并创建 `vX.Y.Z` 发布分支。
   复用现有 CI，然后在六个原生 runner 上检查运行时前置条件、安装依赖、
   Debug 构建、测试、Release 打包、检查二进制架构。
4. 六个新的 consumer runner 下载构建产物并实际安装：Windows NSIS、
   macOS DMG、Linux DEB。安装后的程序必须存活通过冒烟窗口。
   此检查不等同于模型推理、完整安装向导或 UI 功能验收。
5. 六个目标全部成功后，汇总版本、源码 SHA、文件哈希到
   `release-manifest.json` 和 `SHA256SUMS`，上传候选 Release。
   上传可续传，但遇到同名不同内容会失败，绝不覆盖。
6. 自动创建 promote → main 与 rebase → dev PR。先将 promote PR 以
   **merge commit** 合入 main，保留原发布提交的祖先关系，不能 squash。
7. 从 main 手动运行 `Promote release`，输入候选 tag。它验证 main 已包含
   源码提交、该提交有成功的 Release 工作流、六目标清单和实际下载哈希。
   通过后将原始候选字节晋升正式版，更新 latest，再下载校验一次。
8. 合并开发线同步 PR，归档记录。现有清理工作流只删除已合并分支。

手动重跑 `Release` 时，workflow 的 ref 选择对应 tag，tag 输入保持一致，
确保 GitHub 运行记录的 head SHA 与候选源码一致。优先使用原运行的
“Re-run failed jobs”，复用成功目标的产物；整个重建不保证逐字节可复现，
如与已上传候选包不同，必须使用新的版本。

## 原生 runner 与产物

| 目标 | runner | 产物 |
|---|---|---|
| windows-x86_64 | windows-2022 | NSIS .exe |
| windows-arm64 | windows-11-arm | NSIS .exe |
| macos-x86_64 | macos-15-intel | .dmg |
| macos-arm64 | macos-15 | .dmg |
| linux-x86_64 | ubuntu-24.04 | .deb |
| linux-arm64 | ubuntu-24.04-arm | .deb |

统一命名：`ssui-vX.Y.Z-<platform>-<architecture>.<extension>`。
Linux 当前构建基线为 Ubuntu 24.04，不承诺兼容更老的 glibc/WebKit。
其他最低系统要求需经目标系统验收后写入 Release notes，runner 版本本身
不是最低支持版本证明。签名、公证凭据当前未配置，不宣称安装包已签名。

## 仓库配置

- 保护 main、dev 和发布 tag，禁止强推 tag、限制发布权限。
- 启用 Actions 创建 PR 权限；main 要求 main-gate。
- 创建 `release` Environment，配置负责人的 required reviewers，并限制
  deployment branch 为 main。仅声明 environment 名称不会自动启用审批。
- 六种 runner 均需可用；任何目标失败、取消或跳过均不允许晋升。
- 本次代码修改不会自动更改远端保护规则或发布正式版本。

## 运行时配置与验证

`dependencies/runtime-targets.json` 是桌面安装器、依赖生成器、离线包和 CI
共同使用的运行时注册表。发布默认值由 `runtime.cjs` / `runtime_config.py`
读取；Windows ARM64 使用原生 Python 3.12.15 / 20261021，其余目标保留
Python 3.12.8 / 20241219，uv 固定为 0.13.5。

Linux ARM64 使用独立的 `linux-arm64.lock`，原生 CPU PyTorch 2.8.0 /
torchvision 0.23.0 / torchaudio 2.8.0，不复用 x86_64 CUDA 锁文件。
Linux 构建任务在安装依赖前安装 GL/X11 编译头文件。
macOS Intel 使用独立的 `macosx-x86_64.lock`（PyTorch 2.2.2、NumPy 1.x），
避免复用没有 Intel wheel 的 PyTorch 2.4.1；Numba 0.62.1 / llvmlite 0.45.1
固定为仍提供 Intel wheel 的组合。Apple Silicon 保留已有锁文件。

Windows ARM64 使用 `windows-arm64-cpu.lock` 的原生 CPU PyTorch 2.9.1
及配套 torchvision、源码编译的 torchaudio、VTK、OpenCV、PyMeshFix、
pynini 等原生 wheel，不使用 x64 后端转译。编译配方和产物由
[sunxfancy/ssui-python-packages](https://github.com/sunxfancy/ssui-python-packages)
维护；版本和专用索引固定在 `dependencies.yaml`，生成的 lock 用于安装。
缺少 wheel 时必须在该包仓库编译、验证并发布，再更新 SSUI 依赖锁；
终端用户和桌面发布任务均禁止临时源码构建。具体构建记录与原生 CPU
能力边界见 [WindowsArm64Dependencies.md](WindowsArm64Dependencies.md)。

`windows-arm64-wheels.yml` 可单独手动运行，也由 Release 复用。它在原生
`windows-11-arm` 全新环境安装完整锁文件，执行依赖一致性检查、Torch /
torchvision 算子、全部已安装 DLL/PYD 的 PE 架构检查、24 项音频/视频/3D/
图像运行探针和 wheel 可用性审计。报告保留为 `windows-arm64-verification`
artifact。Linux ARM64 和 macOS Intel 另在对应原生 runner 完整安装锁文件、
检查依赖一致性并运行核心推理算子。

sounddevice wheel 附带但不会加载的四个 x86/x64 PortAudio DLL
单独记录，另外验证其实际加载的 PortAudio 为 ARM64。debugpy 通用 wheel
附带的六个旧 CPython/x86 调试辅助文件同样单独记录；实际启动原生 Python
调试服务器并检查加载的扩展。任一缺包、实际运行库
架构错误或探针失败均阻止发布。

Release 新增 `check_runtime.py`：在目标 runner 验证 Python 版本、后端架构，
实际执行 Torch CPU 运算及 torchvision NMS，并导入核心推理库。
跨平台依赖解析和下载地址检查不能替代六个原生 runner 的实际运行验收。

GPU 真模型测试沿用现有独立流程；发布负责人须记录候选 SHA 对应的模型测试
结果。当前工作流没有把 GPU 测试结果自动接入晋升门禁。

## 故障恢复

- 临时网络或 runner 故障：重跑失败 jobs，版本与源码不变。
- 源码、工具链、依赖变化：准备新的版本提交和 tag，完整重测。
- 上传部分成功：重跑汇总上传步骤，已有文件必须逐字节一致。
- PR 权限不足：按日志手动创建 PR，候选版保持未晋升。
- 发布后检查失败：由负责人将 latest 恢复到上一已验证版本，标注问题版本，
  发布修复版本。不得静默替换旧安装包，也不能撤回用户已经下载的文件。

## 本地验证

```sh
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
python3 scripts/release.py check-versions
yarn build:desktop_ui
```
