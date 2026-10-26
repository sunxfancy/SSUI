# 测试指南

## 日常前端验证

根目录执行：

```bash
SSUI_CI_SKIP_INSTALL=1 yarn install --frozen-lockfile
yarn test:frontend
yarn test:ui:install
yarn test:ui
```

Linux 缺少浏览器系统库时执行 `yarn test:ui:install --with-deps`。
`test:frontend` 运行完整组件 Jest 测试和 Functional UI 状态/请求回归测试。
`test:ui` 自动在独立端口 17420 启动真实 Functional UI Vite 页面并运行 Chromium，
无需 Python、模型、GPU 或桌面壳。端口占用时直接失败，避免误测其他服务。

## 浏览器覆盖与边界

- 设置：主题、复选框、文本持久化与重新加载；自动保存失败保留编辑、手动重试。
- Functional UI：执行中禁用函数选择、错误可见、重试成功；元数据读取失败。
- Monaco：键盘编辑与保存、版本传递、409 冲突保留文本、后续保存使用新版本。
- 文件不存在时禁止保存；视图切换保留中文、空格、`&`、`#` 路径。

浏览器测试只模拟 HTTP 服务边界，真实渲染应用及编辑器。每例独立浏览器上下文，
未声明的 API 请求与未捕获浏览器异常均导致失败。新增场景在 `tests/ui/` 编写，
使用 `fixtures.ts` 的 `test` / `expect`，优先通过角色或可访问名称操作。
等待可观察状态或请求，避免固定时间休眠。不要以重试掩盖稳定复现的失败。

以上 Functional UI 浏览器套件不证明真实 Python/模型执行、Tauri IPC、原生文件对话框
或安装包可用，也未建立截图像素基线。桌面 IPC 与原生命令另由下面的套件验证。

## 调试和 CI

```bash
yarn test:ui:headed
yarn test:ui --grep "Monaco"
yarn test:ui:report
```

失败自动保留截图、录像和 trace；HTML 报告在 `playwright-report/`，
附件在 `test-results/`。CI 独立运行前端及浏览器门禁，上传证据保留 14 天。
CI 禁止 `.only`，失败最多重试一次；本地不自动重试。

`yarn test` 保留现有 Python 测试入口；`yarn test:all` 执行前端、浏览器、Rust、原生及 Python 测试。
修改 TypeScript/React 后还需在对应子包执行 `yarn build`。

## Tauri 本地命令测试

| 命令（根目录） | 验证内容 | 环境要求 |
|---|---|---|
| `yarn test:desktop` | Provider 命令名、参数、状态对象、并发锁和重试 | Node.js |
| `yarn test:desktop-ui` | 真实浏览器中的按钮状态、错误展示和 IPC 模拟 | Chromium |
| `yarn test:rust` | 真实子进程、Python 参数/输出、端口释放、本地 HTTP 下载和解包 | Rust、Tauri 系统库、Python |
| `yarn test:native:build` | 类型检查并构建独立测试资源和原生测试程序 | Rust、Tauri 系统库 |
| `yarn test:native` | 真实 WebView → Provider → IPC → Rust → 操作系统 | 已构建测试程序、图形显示环境、Python |

Linux 无图形环境时：

```bash
yarn test:native:build
xvfb-run -a yarn test:native
```

Python fixture 只使用标准库，不安装模型或业务后端。可通过 `SSUI_TEST_PYTHON`
指定解释器。每例使用中文/空格路径的独立临时目录与动态端口；不访问用户安装目录。
完整 `test:all` 在 Linux 无头环境也需要通过 `xvfb-run -a` 执行。

原生测试使用 `desktop/test/native` 的独立控制页面，复用生产 Provider 和完整命令注册表，
不启动生产主页面的自动安装/自动启动流程。因此它证明本地命令闭环，不能替代完整产品导航验收。
覆盖服务与执行器启动、重复启动、状态、重启、停止、启动失败恢复、端口释放，
以及真实 Python 输出和 Store 跨应用重启持久化。
下载测试仅使用回环 HTTP 服务，验证文件字节、SHA256、HTTP 失败、进度/完成/失败/取消事件，
取消后必须关闭正在传输的 HTTP 请求，不能生成完成文件。

嵌入式 WebDriver 依赖为可选 `native-tests` feature，只在独立 `ssui-native-test` example 目标启用（产物在 `target/debug/examples/`）。
测试配置通过 build.rs 同时提供给 Tauri 构建和代码生成，保证资源、权限和应用标识一致。
生产构建不含控制页面与驱动；不要为正式发行开启此 feature。
驱动依赖要求较新的 Tauri 2，Cargo.lock 已更新相关依赖。

原生失败截图、页面和应用日志在 `native-test-results/`；测试 CI 在 Linux、Windows、macOS
分别运行 Rust 与原生套件并上传证据。平台结果以对应 CI 作业为准。

既有 GPU 硬件探测和外部模型/Python 大文件下载测试带 `ignore` 标记，普通门禁不运行。
在具备对应硬件/网络条件的环境，显式执行 `yarn test:rust:external`。
暂停/恢复下载、原生文件选择对话框、真实模型推理及发行安装包仍需独立验收。
