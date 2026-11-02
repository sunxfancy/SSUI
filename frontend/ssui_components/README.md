# 共享组件库

`ssui_components` 提供桌面、Functional UI 和扩展复用的 React 控件、工作流状态与控制器。公开入口是 `src/index.ts`；新增对外 API 应在该文件导出。`src/api/generated.ts` 是从服务端 OpenAPI schema 生成的类型，请使用根目录的 `yarn api:types` 更新，并运行 `yarn api:check` 核对。

本包没有独立 `dev` 脚本。在本目录运行 `yarn build` 生成 `dist/` 和类型声明，运行 `yarn test` 执行 Jest 测试。也可在仓库根目录运行 `yarn build:components`、`yarn test:components`。修改共享组件后，应重新构建，再验证受影响的消费包。独立查看组件场景可在根目录运行 `yarn storybook`；见 [Storybook 指南](../../doc/Storybook.md)。
