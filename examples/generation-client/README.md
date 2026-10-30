# SSUI 开放生成协议原型

SSUI 提供与调用方无关的生成服务。编辑器、游戏引擎、命令行程序及 LLM 的工具适配器都可以通过 HTTP 调用。EVEngine 是潜在客户端之一，不是协议的一部分。此为自定义协议草案，尚非正式行业标准。

运行 `yarn dev:bridge`，打开 http://127.0.0.1:7423 。无需模型、Executor 或引擎。页面使用通用编辑器示例演示预览、应用和撤销，这些操作均由客户端管理。

## v1 契约

基础路径 `/api/generation/v1`，OpenAPI 位于 `/openapi.json`，交互文档位于 `/docs`。

- `GET /capabilities`：协议名、版本、支持能力和原型限制。
- `GET /recipes`：配方 ID、输入 JSON Schema 和产物描述 schema。
- `POST /jobs`：提交任务，返回 202 与完整任务对象。
- `GET /jobs/{jobId}`：查询 queued/running/succeeded/failed/cancelled 状态。
- `POST /jobs/{jobId}/cancel`：取消；终态不变。
- `GET /artifacts/{artifactId}`：下载产物。

```json
{
  "recipe": "mock.checker@1",
  "clientId": "my-editor-session",
  "idempotencyKey": "request-001",
  "inputs": {"prompt": "red brick", "size": 256, "seed": 0},
  "context": {"documentId": "drawing-1", "revision": 2}
}
```

`recipe` 是版本化字符串，客户端先查询可用配方。`inputs` 是由对应配方 schema 校验的 JSON 对象，不在公共请求模型里固定图像参数。目前只实现模拟棋盘配方，提示词仅影响颜色，不执行语义生成。

`context` 可省略，为最多 32 个顶层键的 JSON 对象，SSUI 原样回传，不解释对象 ID、图层、时间线或版本，不依据 context 决定生成行为。客户端也可以仅在本地保存 jobId 到自身目标的映射。不要放入密钥。

`clientId` 是幂等命名空间，不是认证身份。相同 clientId + idempotencyKey 和请求内容返回同一任务；内容不同返回 409。幂等记录只在当前进程生命周期有效。未知配方返回 404，输入校验失败返回 422，任务容量耗尽返回 429。

产物统一描述 `artifactId`、`kind`、`mimeType`、`url`、`sha256`、`metadata`。图像尺寸与色彩空间放在 metadata，不包含材质槽等调用方概念。URL 相对服务地址解析，不是共享文件系统路径。客户端下载后可验证 SHA256，再自行导入、预览或保存。

## 分工与演进

SSUI 管理配方、生成任务与产物；客户端管理目标关联、冲突检查、应用和撤销。MCP 可作为同一业务 API 的适配层，当前未实现 MCP 服务。后续可增加新的配方执行器、输入资源上传、事件订阅与持久化，不需要在公共协议中增加调用方专用字段。

此版本替换早期 `/api/integration/v1` 和必填 target 原型，不保留旧路由。正式 SSUI server 也挂载新路由；独立演示使用 7423，正常服务使用 7422。

## 原型限制及验证

仅用于可信本机开发，独立服务绑定 127.0.0.1。尚无认证、多用户隔离、持久化与事件推送。最多保留 128 个任务；重启清空任务和素材。浏览器刷新清空客户端示例状态。当前仅实现 PNG 模拟输出，不代表已支持视频或音频生成。

`yarn test:bridge` 验证任务、取消、产物下载、幂等隔离、任意客户端 context 和配方校验。`yarn api:types` 同步 OpenAPI 与 TypeScript 契约。
