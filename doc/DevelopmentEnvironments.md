# 多 worktree 开发：共享模型与可选 Python 环境

每个 worktree 可在根目录创建 `.ssui-dev.json`（已被 Git 忽略），参考根目录
`.ssui-dev.example.json`。示例中的路径只是占位，可全部替换，程序不指定共享目录。

配置项：

- `SSUI_VENV_PATH`：虚拟环境根目录，可指向多个 worktree 共用的环境，或该任务专用的环境。
- `SSUI_MODEL_DIR`：模型安装复制目标、后端模型加载默认目录，以及 Wan/Qwen/MiniMax 的本地模型根目录。
- `TEST_DATA_DIR`：真实模型测试下载与读取目录，继续兼容原有变量。
- `HF_HOME`：Hugging Face 缓存目录。
- `TORCH_HOME`：PyTorch Hub 缓存目录。

模型文件、测试数据、缓存与 venv 独立选择。`SSUI_MODEL_DIR` 不会重写工作流中明确传入的模型路径；
各扩展专用的 `SSUI_WAN_MODEL_ROOT` 等变量仍优先。显式下载目标和 Hugging Face 的
`HF_HUB_CACHE` 等更具体的库配置也保持原有优先级。

默认自动读取 `~/.ssui-dev/config.json` 作为机器统一配置；每个 worktree 可用本地文件覆盖部分配置。
显式指定 `SSUI_DEV_CONFIG` 时只读取指定文件。
优先级：进程环境变量 > worktree 配置文件 > `~/.ssui-dev/config.json` > 原有默认值。文件中相对路径相对于配置文件所在目录，
机器配置相对路径相对于 `~/.ssui-dev/`；环境变量中的相对路径相对于当前 worktree 根目录，支持 `~/`。
未配置时仍使用当前 worktree 的 `.venv`，模型和缓存保留原有默认位置。

## 一份配置供多个 worktree 使用

将示例文件复制到自己选择的机器配置位置，修改其中路径。在各终端设置：

```powershell
$env:SSUI_DEV_CONFIG = 'E:/my-config/ssui.json'
yarn dev:paths
```

`SSUI_DEV_CONFIG` 可指向任意 JSON 文件；指定文件不存在、JSON 错误或路径类型错误会直接报错。
`yarn dev:paths` 显示解析后的配置，无需安装 Python 包。

## 根据任务选择环境

普通 UI、业务逻辑、使用既有依赖的功能开发，可在配置中让 `SSUI_VENV_PATH` 指向同一个环境。
首次准备该环境可运行 `yarn`；后续 worktree 只需要安装 JS 依赖时可跳过 Python 安装：

```powershell
$env:SSUI_CI_SKIP_INSTALL = '1'
yarn
Remove-Item Env:SSUI_CI_SKIP_INSTALL
```

依赖升级、Torch/CUDA 变更、不同依赖锁或验证安装流程的任务，覆盖为独立环境：

```powershell
$env:SSUI_VENV_PATH = '.venv'
yarn
yarn test
```

这只切换 venv，模型和缓存继续使用机器配置中的目录。也可以指定任意绝对路径作为任务环境。
恢复共享环境：`Remove-Item Env:SSUI_VENV_PATH`。
任务类型由开发者明确选择，程序不会猜测并自动切换或迁移已有环境。
共享环境的安装、升级会影响所有使用者，不要在多个 worktree 中同时安装或用它测试不同依赖集。

## 生效范围与验证

`yarn dev:server`、`yarn dev:server:no_build`、`yarn dev:executor`、`yarn test`、
`yarn test_on` 和 `node dependencies/venv.cjs ...` 都通过统一环境入口启动。
`yarn dev:desktop` 将配置传给 Tauri，开发构建的 Python 子进程使用所选环境；
直接运行 Tauri CLI 不会读取本地 JSON，需自行提供环境变量。正式安装包保持安装器的解释器选择。
`yarn install-requirements`、`yarn update-lock` 和 `yarn pack-offline` 也使用所选环境。
`yarn requirements` 的中间文件写到当前 worktree 的 `.build`，不会覆盖共享 venv 中的文件。

共享环境不执行当前仓库的 editable install；启动器通过 `PYTHONPATH` 优先导入当前 worktree，
避免一个 feature 安装后影响另一个 feature 的源码定位。直接调用共享 Python 时需自行设置源码路径。
直接在 Python 中启动服务时支持环境变量，但不读取开发 JSON。

`yarn test:dev-config` 验证配置优先级、跨 worktree 共享、独立环境覆盖和子进程启动。
真实模型回归继续通过 `SSUI_RUN_MODEL_TESTS=1 yarn test` 启用。
已有模型不会自动搬迁；请让配置指向已有目录，或自行迁移后更新路径。

此配置解决磁盘资源与 Python 环境复用。多份服务同时运行仍需配置独立端口
（服务端支持 `SSUI_SERVER_PORT`）；桌面的自动服务探测和前端开发端口仍沿用当前逻辑。
