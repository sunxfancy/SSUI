# 运行目标：OS、架构与计算后端

运行目标使用三个独立字段：

```ts
interface RuntimeTarget {
  os: 'windows' | 'linux' | 'macos';
  arch: 'x64' | 'arm64';
  backend: 'cpu' | 'cuda' | 'rocm' | 'mps' | 'qnn';
}
```

`dependencies/runtime-targets.json` 登记目标维度、Python triple 和已提供依赖的目标。
`dependencies/dependencies.yaml` 是 Python 包声明的唯一维护入口。
Python 和桌面编译目标只取决于 OS + arch；依赖配置取决于全部三个字段。
GPU 厂商不能代替计算后端，检测到硬件也不代表该后端已可运行。

## 依赖组合配置

维护一份 YAML，按固定顺序组合：

```text
common → os[目标 OS] → arch[目标架构] → backend[目标后端] → 匹配的 overrides
```

配置结构示例（省略了实际包列表）：

```yaml
version: 1
common:
  packages:
    fastapi[standard]: ">=0.115.6"
os:
  windows: {}
  linux: {}
  macos: {}
arch:
  x64: {}
  arm64: {}
backend:
  cuda:
    packages:
      torch: "==2.4.1+cu124"
    extraIndexes:
      - https://download.pytorch.org/whl/cu124
  mps:
    packages:
      torch: "==2.4.1"
overrides:
  - when:
      os: windows
      arch: x64
      backend: cuda
    packages:
      triton-windows: "==3.1.0.post17"
```

- 后一层的同名包替换前一层约束；包名忽略大小写，`-`、`_`、`.` 等价。
- 包 extras 是声明的一部分，替换包时也替换 extras，不自动合并。
- 值为 `null` 时删除包。多个约束用数组表示，生成多条要求，由 pip/uv 求交集。
- 直链写作 `包名: "@ https://...whl"`；保留真实 wheel URL，不猜测或替换架构后缀。
- `extraIndexes` 跨层累加并去重，不因替换单个包隐式删除索引。
- `when` 可筛选任意一个或多个维度，数组表示该维度任选一个；不同维度之间为 AND。
- 多条匹配的 override 按文件顺序应用，后者优先。未知维度、字段、重复包名等配置错误直接报错。

只为 runtime-targets.json 中登记的目标生成可发布 requirements；能够表达某个组合不代表其依赖已验证。
新增目标时应检查复用各层后的完整结果，公共包本身也可能缺少该系统/架构的 wheel。

## 生成与维护命令

```powershell
# YAML 修改后，生成所有已登记目标的兼容 txt
yarn requirements:generate

# 也可只生成一个目标（接受三维名称或现有兼容名）
yarn requirements:generate --target windows-x64-cuda

# 检查提交的生成文件是否过期，不写文件、不访问网络
yarn requirements:check

# 自动生成对应 txt，再调用 uv 解析目标平台的完整 lock
yarn update-lock --target windows-x64-cuda
yarn update-lock:all
```

`requirements-*.txt` 保留为带有 DO NOT EDIT 标记的生成产物，兼容已有 Python-only CI。
不再人工维护这些文件；CI 会检查它们与 YAML 是否一致。
每个已发布目标仍需要独立的 lock，因为解析后的版本、依赖和 wheel 资源可能不同。
本次迁移保留五个原始 requirements 的所有有效包约束、直链及索引，未升级或重新生成现有 lock。

`yarn requirements` 直接从 YAML 组合当前目标，再追加扩展 manifest 声明，写入 `.build/requirements.txt`。
扩展约束保留 PEP 440 原文，交给 Python 解析器求交集，不再用 JavaScript semver 改写。
`yarn install-requirements` 继续安装已生成的目标 lock，不直接安装这个开发用合并文件。

## 已有依赖配置

| OS | arch | backend | 兼容的依赖文件名 |
| --- | --- | --- | --- |
| windows | arm64 | cpu（实验） | windows-arm64-cpu |
| windows | x64 | cuda | windows |
| windows | x64 | rocm | windows-amdgpu |
| linux | x64 | cuda | linux |
| linux | x64 | rocm | linux-amdgpu |
| macos | arm64 | mps | macosx |

这些映射保留已有 requirements、lock 和发布工作流的文件名；它们不代表所有模型都支持对应后端。
例如 AMD 依赖仍有 CUDA wheel，需要另行清理，当前改动不验证其模型兼容性。
新增配置可使用 `windows-arm64-cpu` 一类三维文件名，而不增加新的 OS 枚举值。

Windows ARM64 CPU 已提供仅预编译包的实验配置和独立 lock，详见
[依赖审计报告](WindowsArm64Dependencies.md)。它使用原生 Python 3.12.15 / 20261021、
uv 0.13.5；已有目标继续使用原来的 Python 和依赖版本。
Linux ARM64 CPU、macOS x64 CPU、QNN 尚未提供依赖配置。
缺少配置时明确报错，不回退到 x64、CUDA 或其他系统的 lock。
不能把 lock 解析通过等同于全部工作流支持；实验目标移除了缺少兼容 wheel 的组件。
QNN 仅保留标识，不会自动启用，也没有在本次改动中实现模型转换或 NPU 推理。

## 检测与显式选择

Node 脚本区分宿主架构、当前 Node 进程架构、请求的目标架构。
Windows 下用 PROCESSOR_ARCHITEW6432 / PROCESSOR_ARCHITECTURE 辅助识别宿主；
默认按当前进程架构选择 Python，防止 x64 模拟运行时混装 ARM64 wheel。
非 Windows 下的宿主架构暂以进程架构表示，不额外探测 Rosetta。
桌面端按 Tauri 应用编译架构选择安装目标。

macOS ARM64 默认选择 MPS，Windows/Linux ARM64 默认 CPU。
为兼容现有依赖，Windows/Linux x64 的 AMD GPU 默认选择 ROCm，其余默认选择已有的
CUDA 依赖分发（PyTorch 可在该分发中回退到 CPU）；这不代表已检测到可用 CUDA。

Node 维护脚本允许独立覆盖各维度：

```powershell
$env:SSUI_TARGET_OS = 'windows'
$env:SSUI_TARGET_ARCH = 'arm64'
$env:SSUI_COMPUTE_BACKEND = 'cpu'
```

覆盖不意味着支持该组合。依赖安装会校验实际 Python 的 OS / 架构。
`yarn update-lock` 按当前 OS + arch 生成已有后端配置，`--all` 显式解析全部配置；
解析时传入目标 Python 平台与版本，避免按宿主机器生成错误的锁文件。
`yarn pack-offline --target windows-x64-cuda` 也接受兼容名 `windows`，输出仍用兼容名。
离线下载要求实际 Python 与目标 OS / arch 一致；manifest 保存完整三维目标，桌面安装时验证。
旧版 manifest 可由固定的兼容名推断目标。

## 验证

```powershell
yarn test:runtime-target
yarn test:dependency-config
yarn requirements:check
yarn build:components
yarn build:desktop_ui
```

后续增加更多 ARM64 支持时，应补充 YAML 中的依赖层和覆盖规则、登记目标，
生成对应 requirements / lock 并验证 Python 下载资源，再加入 ARM64 构建、安装及真机测试。
构建矩阵同样应独立记录 OS、arch、backend，
不能直接把宿主架构当成目标架构。当前发布矩阵保持不变，尚不发布 Windows ARM64 安装包。
