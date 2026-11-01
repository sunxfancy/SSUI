# 无后端 UI 与插件开发

在仓库根目录执行 `yarn storybook`，打开 http://localhost:6006。
旧命令 `yarn dev:desktop_sb` 仍然可用。无需启动 FastAPI、executor、Python 虚拟环境或 Tauri，
也无需预先构建共享组件。Storybook 直接引用 `ssui_components` 源码，修改后热更新。

统一配置与公共 mock 位于根目录 `.storybook/`，依赖与命令由根 `package.json` 管理。
desktop 中的旧命令保留为根命令的转发入口。

全新 checkout 如只开发 UI，可在安装依赖时跳过 Python 安装：

```powershell
$env:SSUI_CI_SKIP_INSTALL = '1'
yarn install --frozen-lockfile
yarn storybook
```

## 入口与场景

- `Components`：桌面导航、工作区、标签、安装、扩展、任务队列、模型源。
- `Components/Model adding`：完整添加模型页面，可切换预设、Civitai、Hugging Face、本地模型；子故事提供预设包、搜索结果、空结果、扫描和失败场景。本地选择目录、扫描、添加及 Civitai 下载通过内存 provider 演示；预设/Hugging Face 下载只模拟任务入队，不执行真实下载。
- `Shared`：通过真实组件注册系统选择文本、数字、布尔、图片、列表等输入/输出组件。
- `Functional`：函数运行台（可点击运行）、高级参数、工作流编辑器、模型、设置、代码编辑器、图片预览。
- `Extensions`：Image Canvas 与 example 插件。

这是各 UI 的独立开发入口，不模拟模型推理。没有前端入口的 Python 插件（例如 Audio、Video）
可通过共享音视频组件预览其 UI；Python 执行与 VS Code 扩展宿主仍需各自的集成环境。
当前故事覆盖上述入口及部分状态；新增业务页面仍需添加自己的故事与数据，不能把静态构建成功当成全部交互覆盖。

## 新增 UI / 插件

故事与源码相邻放置，文件名为 `*.stories.tsx`。以下位置会自动发现，无需修改全局配置：

- `desktop/src/**`
- `frontend/*/src/**`
- `extensions/*/**`（如 `extensions/MyPlugin/src/Panel.stories.tsx`）

导入组件本身，不导入会挂载 React 根节点或启动服务的 `main.tsx`。
使用 `Components/…`、`Shared/…`、`Functional/…`、`Extensions/插件名/…` 的标题组织故事。
需要原生能力的组件优先接受 provider；使用现有 mock provider 代替真实安装、文件系统等操作。

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Panel } from './Panel';

const meta = {
  title: 'Extensions/MyPlugin/Panel',
  component: Panel,
  parameters: {
    offline: {
      routes: {
        'GET /api/my-plugin/items': [{ id: 'demo', name: '示例' }],
      },
    },
  },
} satisfies Meta<typeof Panel>;
export default meta;
export const Ready: StoryObj<typeof meta> = {};
export const Empty: StoryObj<typeof meta> = {
  parameters: { offline: { routes: { 'GET /api/my-plugin/items': [] } } },
};
export const Loading: StoryObj<typeof meta> = {
  parameters: { offline: { delay: 30000 } },
};
export const Error: StoryObj<typeof meta> = {
  parameters: { offline: { routes: {
    'GET /api/my-plugin/items': () => new Response('读取失败', { status: 500 }),
  } } },
};
```

## Mock 约定

`parameters.offline.routes` 用 `METHOD /pathname` 匹配请求，忽略 host/port。
handler 可用 `({ url, input, init }) => …` 读取 query、请求或 body，返回 JSON 数据或新的 `Response`。
不要直接存放可重复消费的 `Response` 实例。每个故事进入前都会重设路由；同路径的故事配置覆盖默认 fixture。
延迟支持 AbortSignal。默认数据位于 `.storybook/mocks/fixtures.ts`。

预览内的 fetch 与 axios 请求使用同一套 mock。未声明的业务请求以及外部 fetch 会报
`[Storybook offline] Missing mock: …`，不会回退到真实 API。Vite 的 API proxy 已禁用。
`/ws` 使用静态离线会话，不推送任务或执行进度；需要进度、流式结果时，为组件注入专用服务/provider。
未知 socket 地址和发送消息会明确报错。Tauri 提供固定路径/平台及文件选择模拟，未知 invoke 命令会报错。
这些替换仅在 Storybook 配置中生效。

fetch mock 不拦截 `<img>`、`<video>`、iframe、下载链接或第三方直接创建的 XMLHttpRequest。
媒体故事应传入 data URL、本地静态资源或 URL resolver（参考 ImagePreview 故事），
不要使用指向后端的资源地址。axios 已专门切换为 fetch adapter。
新增插件使用其他网络客户端时，应注入 mock transport，并在浏览器中检查无 API 请求。

队列传入 `items`（包括 `[]`）时进入本地预览：禁用轮询、WebSocket 和服务状态检查，
删除、取消、清除操作只修改演示列表；不传 `items` 时按正常应用行为加载任务。

## 验证

```bash
yarn test:storybook    # 离线请求路由、错误、隔离及取消测试
yarn build:storybook   # 构建全部故事到 storybook-static
```

CI 在 Linux 上执行上述两项，且放在 Python 环境配置之前。
本地开发时检查 Ready / Empty / Loading / Error，并实际操作保存、执行等按钮。
常规包构建仍使用根目录或各包 `package.json` 中的 yarn 命令。
