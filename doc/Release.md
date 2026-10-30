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

`dependencies/runtime.json` 是 Python 版本、发行日期、uv 版本、目标架构与
依赖锁文件的共同来源。桌面安装器、开发环境 bootstrap、离线包和 CI 均读取它。
Python 已升级到 3.12.16 / 20261026；六个官方解释器下载地址已验证存在。

Linux ARM64 使用独立的 `linux-arm64.lock`，原生 CPU PyTorch 2.9.1 /
torchvision 0.24.1 / torchaudio 2.9.1，不再复用 x86_64 CUDA 锁文件。
229 个依赖已按 aarch64 + Python 3.12 解析；除 moderngl、glcontext 和纯 Python
transformers-stream-generator 需源码构建外，其余均通过目标 wheel 可用性解析。
Linux 构建任务在安装依赖前安装 GL/X11 编译头文件。

macOS Intel 使用独立的 `macosx-x86_64.lock`（PyTorch 2.2.2、NumPy 1.x），
避免复用没有 Intel wheel 的 PyTorch 2.4.1。Apple Silicon 保留已有锁文件。

Windows ARM64 使用原生 CPU PyTorch 2.8.0，并在 `windows-11-arm` 上编译
缺失的 wheel。torchvision 0.23.0、torchaudio 2.8.0、VTK 9.5.2 与 vcpkg
源码固定到 `windows-arm64-sources.json` 中的 commit；其余缺包按锁定版本
从源码构建，包括 OpenCV、PyMeshFix、ModernGL、glcontext、tiktoken 等。
不使用 x64 后端转译。CUDA 专用扩展需要独立的受支持 GPU 工具链，不能把
CUDA 算子靠重新编译转换成 CPU 算子；本配置覆盖原生 CPU 音频/3D 依赖。

`windows-arm64-wheels.yml` 可单独手动运行，也由 Release 复用。它检查每个
wheel 的平台标签及所有 DLL/PYD 的 PE 架构，然后在全新虚拟环境中离线
安装整个 wheelhouse、执行 pip check、Torch/torchvision 算子、WAV 读写、
重采样、VTK 几何和网格修复测试。任一缺包、架构错误或测试失败均阻止发布。

成功后下载 `windows-arm64-wheels` artifact，将其解压路径设置为
`SSUI_NATIVE_WHEELHOUSE`。桌面打包只嵌入需要源码构建的 wheel；用户安装时
优先使用这些 wheel 且禁止本机源码构建。开发环境 `yarn install-requirements`
和 `yarn pack-offline --target windows-arm64` 使用同一 artifact 的完整 wheelhouse。
manifest 绑定原始锁文件、离线锁文件、Python 版本以及所有 wheel 校验和，
不能复用其他版本的依赖产物。正式 Release 自动传递该 artifact，无需手动设置。

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
