# 模块导航

从开发目标进入对应模块的 README；跨模块关系见 [架构说明](Architecture.md)，构建和测试命令见 [构建指南](BuildSystem.md)与[测试指南](Testing.md)。

| 模块 | 职责 | 入口文档 |
| --- | --- | --- |
| Desktop | Tauri 桌面壳、安装与服务管理 | [desktop/README.md](../desktop/README.md) |
| Server | FastAPI 路由、服务与任务调度 | [server/README.md](../server/README.md) |
| Executor | 独立进程中的脚本执行 | [ss_executor/Readme.md](../ss_executor/Readme.md) |
| Backend | 模型管理、推理与原生工具 | [backend/README.md](../backend/README.md) |
| Functional UI | 工作流与设置界面 | [frontend/functional_ui/README.md](../frontend/functional_ui/README.md) |
| Shared components | 共享 React 控件、状态与 API 类型 | [frontend/ssui_components/README.md](../frontend/ssui_components/README.md) |
| Canvas Engine | Rust/Wasm 画布引擎 | [packages/canvas-engine/README.md](../packages/canvas-engine/README.md) |
| Extension builder | `ssext` 扩展创建与打包 | [extension_builder/README.md](../extension_builder/README.md) |
| Extensions | Image、Video、Audio、3D、Motion 等扩展 | [扩展目录](../extensions/Readme.md) |
| VS Code | 脚本开发插件 | [ssui-vscode/README.md](../ssui-vscode/README.md) |
