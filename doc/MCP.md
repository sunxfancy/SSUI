# MCP Server

SSUI 提供本地 stdio MCP Server，覆盖后端 API、扩展 SDK/示例发现、桌面原生命令、工作区、代码/Flow 编辑和 Image 画布。
它复用正式 HTTP API、SSExecutor 和正在运行的 UI 对象，不加载第二套模型。
目标是让项目实际存在的功能都可被发现和调用；OpenAPI 自动接入新 API，扩展 SDK 从源码发现，UI 注册自身命令及参数 schema。

## 安装和启动

在仓库根目录执行（Python 3.10+，使用项目配置的虚拟环境）：

```sh
yarn install:mcp
```

启动桌面软件，或分别运行 `yarn start:server` 与 `yarn dev:executor`。
默认后端为 `http://127.0.0.1:7422`。MCP 由客户端按需拉起：

```sh
yarn start:mcp
```

该命令等待 stdin 中的 MCP 消息，并非交互式命令行。客户端配置请直接使用 Node 入口，避免 yarn 日志污染 stdio。

## MCP 客户端配置

将下面配置加入客户端的 MCP 配置文件，替换两个绝对路径：

```json
{
  "mcpServers": {
    "ssui": {
      "command": "node",
      "args": [
        "C:/path/to/SSUI/dependencies/venv.cjs",
        "python", "-m", "server.mcp_server",
        "--url", "http://127.0.0.1:7422"
      ],
      "cwd": "C:/path/to/SSUI"
    }
  }
}
```

客户端需支持 `cwd`；否则使用启动脚本先切换到仓库目录。
也可用 `SSUI_MCP_URL` 指定后端，`--url` 优先。只接受 loopback HTTP origin。
`--timeout` 默认 600 秒；请求超时不会取消已排队/执行的任务，先查询任务再决定是否重试。
MCP 依赖为 `.[mcp]` 可选依赖，不改变原有桌面和平台模型依赖。

## 原生服务、安装和重启

已运行后端会提供 UI 命令中继，但停止后端也会断开该通道。
需要安装、启动/停止/重启服务时，先在独立终端运行：

```sh
yarn start:agent
```

这是独立的本地中继（`127.0.0.1:7424`），不依赖模型服务器。
给 MCP 客户端 `args` 追加 `"--ui-url", "http://127.0.0.1:7424"`。
桌面 Root 自动连接它，因此安装页也能注册原生命令和表单操作。
修改后的桌面前端需重新构建/启动；旧版已运行桌面不会自动出现这些命令。
服务重启时请求可能返回断连错误；等待重连、刷新 target 列表，再查询实际状态，避免重复安装或启动。

## 全功能接入范围

- **所有后端 HTTP 操作**：`ssui_api_*` 从实际 `/openapi.json` 生成独立工具，保留 path/query/header/body 参数 schema，并在发送前校验。包含配置与文件打开器、模型查询/扫描/安装、HF/ModelScope/Civitai 搜索与下载、预设模型、任务管理、Flow 编译、执行、素材上传/读取、界面状态和扩展自定义 API。后端离线时使用仓库 OpenAPI；`ssui_capabilities` 明确报告 live/fallback 并刷新扩展 API。新增路由无需另外手写 MCP wrapper。
- **上传及二进制结果**：multipart 的文件参数使用 `{filename, data_base64, content_type?}`；二进制下载返回 `{mimeType, data_base64}`。响应上限 20 MiB，大文件使用结果路径和本地文件工具。
- **异步扫描/下载回调**：`ssui_run_callback_api` 接受生成的 API 工具名和参数，先连接 `/ws`，注入 `client_id`，等到 `finish`；返回最近 200 条回调及总条数。直接调用对应 `ssui_api_*` 只返回 start 标识，不能据此判定任务完成。
- **全部第一方扩展 SDK**：`ssui_project_catalog` 分页搜索所有 `extensions/*/ssextension.yaml`、`ssui_*` 中的公开函数/方法和 examples。覆盖 Image、Video、Audio、LLM、Motion、3D 等实际存在的扩展；不导入重型模型代码。先查签名/示例，把需要的 SDK 调用组合进项目脚本，再准备/执行。实例方法仍需先构建或加载对应实例。
- **桌面原生命令**：`native.*` 覆盖 Rust `command_handler()` 全部命令，包括 GPU/端口检测、Python/安装包、前后台 Python、server/executor 启停重启、代理与下载暂停/恢复/取消/进度。参数采用 Tauri 的 camelCase；测试检查源注册项没有漏接。
- **工作区和桌面**：`desktop.*` 打开工作区/文件、查看布局、切换侧栏、打开模型添加和设置、切换语言、关闭单个/其他/全部 Tab。`files.*` 列目录、读取、新建、重命名、建目录、删除。
- **画布**：`canvas.*` 查看真实图层与对象、创建/选择/重排/复制/删除图层、改名称/可见性/锁定/透明度、创建/修改/删除/复制/排序笔迹对象、压力点与 Bezier 节点、工具/画布设置、缩放、撤销/重做、加载图片、保存、导出真实 PNG。修改复用原编辑器历史记录与渲染路径。
- **Flow 编辑器**：`graph.*` 读取图结构、创建/移动/重命名/选中节点、输入输出端口增删改型、连线/断线、函数分组尺寸、缩放适配、清空和持久化。
- **代码编辑器**：`code.*` 读取当前未保存缓冲区、以 expectedContent 检查并修改 Monaco 内容、保存及调用实际编辑器 action。文件保存仍执行磁盘版本冲突保护。
- **其余可见 UI**：`ui.snapshot/click/input/key/pointer/upload` 提供表单、菜单、会话、模型选择、设置、媒体预览、扩展控件与画布指针操作。snapshot 返回当前控件 ID、标签和 bounds；不提供任意 JavaScript eval。

所有 live UI 命令都通过 `ssui_ui_targets` 发现，再由 `ssui_ui_call(target_id, command, arguments)` 调用。
target 列表包含精确的 inputSchema。打开相应编辑器后它才会注册；关闭、切换文件或重载会移除旧 target。
桥接校验本机连接及 Origin，执行前校验 schema，同一页面串行处理命令，并返回实际结果或错误。

## Agent 工作流

1. `ssui_status` 查看后端版本、设备和扩展；`ssui_list_models` 获取已安装模型。
2. 用 `ssui_project_catalog` 搜索扩展/算子/示例；给出本机项目脚本路径，用 `ssui_list_files` 查脚本和素材，或 `ssui_list_operators` 查 Flow 算子。
3. `ssui_inspect_script` 获取 `.py` / `.flow` 的函数名称与类型。
4. `ssui_prepare_script` 获取选中函数的参数配置，然后按配置构造 `params`，必要时传递 `details`。
5. `ssui_execute_script` 执行并返回真实结果，包括脚本生成的文件路径。`ssui_list_tasks` 查看队列状态。
6. `ssui_read_text` 读取脚本或 Flow 及版本；`ssui_save_text` 必须带读取到的 `expected_version`。冲突返回错误，重新读取并合并。

示例指令：

> 使用 SSUI 检查 C:/my-project/workflow.py 的可调用函数和参数，选择已安装模型执行生成，并报告实际输出文件。

脚本发现也可能加载 Python 代码；执行、准备、保存均标记为有副作用。
请连接可信的本机项目；此适配器拥有后端现有文件和执行权限，没有额外目录沙箱。
API 工具的生成不代表每个硬件/模型都可用；源码目录存在的模型也不代表权重已安装。
generation bridge 的 recipe/job/artifact API 是明确标记的 mock prototype，真实推理使用 SSExecutor。
项目尚未实现的功能不会通过 MCP 变成可用功能，例如扩展商店安装/禁用接口和新工作流模板落盘仍有原项目占位逻辑。
输出路径可交给客户端本地文件工具读取，也可使用对应 `/file` MCP API 下载。

MCP 工具数量随运行中扩展的路由变化；live UI 命令数量随当前打开的编辑器变化，不维护另一份必须人工同步的总注册表。

## 验证

```sh
yarn test:mcp
yarn build:frontend
yarn test:mcp:ui
```

`test:mcp` 检查 stdio 握手、全部 OpenAPI 操作映射、schema、扩展动态发现、multipart/二进制、文件版本冲突、WebSocket 路由、跨站拒绝与原生命令覆盖。
`test:mcp:ui` 使用正式构建产物和真实文件/状态/桥接路由，经过 MCP 修改画布、撤销/重做、导出 PNG、编辑/保存/重开 Rete 图及修改 Monaco；模型边界使用无模型 fixture。
需安装 Playwright Chromium；也可设置 `SSUI_TEST_BROWSER_CHANNEL=msedge` 使用已安装 Edge。
只读 Agent 发现能力评估见 [mcp-evaluation.xml](mcp-evaluation.xml)。
这些测试不代表所有 GPU 模型推理或全部原生命令副作用均已通过；真实生成需要 executor、扩展、模型与对应硬件。
