# UI 状态保存

SSUI 项目（包含 `ssproject.yaml`）中的界面状态由服务端保存到项目目录：

```text
.ssui/
  ui_states/    # 按项目相对文件路径和视图隔离的 JSON 状态
  assets/       # 画布图片等临时资源，按内容哈希命名
```

修改后约 300ms 自动保存；切换页面、页面进入后台和组件卸载时尝试立即提交。保存失败会提示并重试。读取失败时提供重试入口，不会用初始值覆盖已有数据。突然结束进程前尚未提交的修改无法保证恢复。

保存范围包括 Functional UI 的函数选择、输入、组件 Tab、高级参数及运行结果，工作流的节点、端口、连线、函数引用、折线控制点和视口，代码编辑器的未保存草稿、光标和滚动位置，以及 Image Canvas 的图层、图片、位置、工具设置和生成参数。请求中状态、错误、弹出菜单等临时交互状态不会保存。设置页面继续使用现有配置服务。

复制项目时应包含隐藏目录 `.ssui`。状态文件以项目相对路径标识，状态值中的项目内文件路径会保存为相对引用，加载时恢复为当前项目的绝对路径。项目外的模型文件或工具路径仍需在目标机器上提供。文件重命名会得到独立状态；不支持的状态版本会报告读取错误。

代码草稿不会自动覆盖源文件，仍由编辑器的 Save 按钮或 Ctrl/Cmd+S 写入源文件。恢复草稿时若磁盘文件已改变，会提示用户检查。

## 新 UI / 扩展接入

共享组件库 `ssui_components` 导出统一 API。独立前端先在入口包裹：

```tsx
<UIStateProvider path={projectFilePath} view="my-extension">
  <MyUI />
</UIStateProvider>
```

`view` 应为稳定且唯一的名称。内置 Functional UI 入口已自动包裹其 UIProvider。项目外文件继续打开，但不启用项目状态保存。

使用 `UIStateScope` 按函数、参数、列表项等建立稳定的层级，名称应使用项目相对路径，避免绝对路径：

```tsx
<UIStateScope name="function-name/input-name">
  <MyInput />
</UIStateScope>
```

函数组件使用 `useUIState('field-name', initialValue)`，返回值和直接设置函数与 `useState` 类似。它的 setter 接受新值，不接受 updater 函数。

类组件可继承 `PersistentComponent<Props, State>`，并指定 `protected persistedFields: (keyof State)[]`。`IComponent` 已继承该基类；`IController` 默认保存 `value` 和 `userInput`。如果覆盖 `componentDidMount` 或 `componentDidUpdate`，需要调用父类对应方法。只指定可 JSON 序列化的持久字段，DOM、React 元素和 ImageBitmap 等运行时对象应保存资源引用并在加载时重建。

## HTTP API

- `GET /api/ui_state_load?script_path=...&view=...`：返回状态对象，首次打开返回 `{}`。
- `POST /api/ui_state_store?script_path=...&view=...`：JSON body 包含 `state_data` 对象。可附加 `client_id` 和递增的 `revision`，防止同一界面关闭时的最终提交被较早请求覆盖。
- `POST /api/ui_state_asset?script_path=...`：multipart `file` 保存到 `.ssui/assets`，返回 `{success, path}`。将 `path` 保存进界面状态即可在复制项目后恢复。

状态通过临时文件加原子替换写入。未传 `view` 时兼容原接口的绝对路径 MD5 状态文件读取。JSON 中使用内部 version/state 包装和项目路径标记，调用方应通过 API 读写。
