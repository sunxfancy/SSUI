# Functional UI

此包是工作流功能界面。`src/main.tsx` 挂载 React 应用与配置 Provider；`src/ui/` 包含工作流、设置等界面；共享控件来自 `ssui_components`。开发服务器默认使用端口 7420。

在仓库根目录运行 `yarn dev:functional_ui` 启动 Vite。若要连实际后端运行工作流，另开终端运行 `yarn dev:server` 和 `yarn dev:executor`。修改共享组件后先运行 `yarn build:components`。

在本目录运行 `yarn build` 检查类型并构建，运行 `yarn test` 执行 Node 与 Vitest 测试。根目录的 `yarn test:ui` 运行浏览器场景；范围和环境要求见 [测试指南](../../doc/Testing.md)。前后端接口见 [通信说明](../../doc/FrontendBackendCommunication.md)。
