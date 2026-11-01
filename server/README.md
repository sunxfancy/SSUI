# Server

`server/` 是 FastAPI 应用。`__main__.py` 负责启动 Uvicorn；`app.py` 的 `create_app()` 组装服务、路由与生命周期，并在启动时检测扩展、启动任务调度器。`routes/` 按配置、模型、脚本、文件、任务、UI 状态、扩展和 WebSocket 划分 HTTP 接口；相应的 `*_service.py` 实现业务逻辑。

## 本地运行

在仓库根目录运行 `yarn dev:server`（先构建前端）或 `yarn dev:server:no_build`（复用已有构建）。独立执行任务时另开终端运行 `yarn dev:executor`。默认服务地址为 `http://localhost:7422/`，交互式 API 文档位于 `/docs`。`SSUI_SERVER_HOST` 和 `SSUI_SERVER_PORT` 可覆盖默认绑定地址与端口。

## 验证和相关文档

根目录的 `yarn test` 运行 Python 测试，`yarn test:contract` 验证模拟 API 契约，`yarn api:check` 检查 OpenAPI schema 与前端生成类型是否同步。修改接口后检查 `server/openapi.json` 和 `frontend/ssui_components/src/api/generated.ts`。整体关系见 [架构说明](../doc/Architecture.md)，前后端调用见 [通信说明](../doc/FrontendBackendCommunication.md)，执行器见 [Executor](../doc/Executor.md)。
