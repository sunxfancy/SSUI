# SSUI 项目指引（供 AI 助手查阅）

修改代码后的**验证、编译、启动**，务必先查看对应目录的 `package.json` 中的 `scripts`，使用项目已定义的命令，不要自行猜测（例如不要直接 `npx tsc`，应使用子项目内的 `yarn build`）。

更详细的构建说明见：`doc/BuildSystem.md`、`doc/Package.md`、`Readme.zh.md`。

---

## Monorepo 结构

根目录 `package.json` 使用 **yarn workspaces**，包含以下子包：

| 目录 | 包名 | 说明 |
|------|------|------|
| `desktop/` | ssui-desktop | Tauri 桌面壳：侧栏、Tab、安装、服务器管理 |
| `frontend/ssui_components/` | ssui_components | 共享 React 组件库 |
| `frontend/functional_ui/` | ssui-functional_ui | 功能 UI（Rete 工作流编辑器等） |
| `ssui-vscode/` | ssui-vscode | VS Code 插件 |
| `extension_builder/` | extension_builder | 扩展打包 CLI（`ssext`） |
| `extensions/Image/` | ssui-image | Image/Canvas 扩展前端 |

不在 workspace 内但有关联的子项目：

| 目录 | 说明 |
|------|------|
| `extensions/example/` | 示例扩展插件（`yarn build:example`） |
| `extensions/Video/`、`extensions/Audio/` | 无独立 package.json，通过 `ssext package` 打包 |
| `backend/`、`server/`、`ss_executor/` | Python 后端，通过 `dependencies/venv.cjs` 调用 |

---

## 验证 / 编译速查

在各子目录执行对应 `yarn build`（或根目录的聚合命令）：

| 修改范围 | 验证命令 | 实际执行内容 |
|----------|----------|--------------|
| `desktop/` | `cd desktop && yarn build` | `prebuild` → `copy-resources` → `tsc && vite build` |
| `frontend/ssui_components/` | `cd frontend/ssui_components && yarn build` | `tsc && vite build` |
| `frontend/functional_ui/` | `cd frontend/functional_ui && yarn build` | `tsc && vite build` |
| `extensions/Image/` | `cd extensions/Image && yarn build` | `tsc && vite build` |
| `extensions/example/` | `yarn build:example`（根目录） | `cd extensions/example && yarn build`（`tsc`） |
| `extension_builder/` | `yarn build:extension_builder`（根目录） | `cd extension_builder && yarn build`（`tsc`） |
| `ssui-vscode/` | `yarn build:vscode`（根目录） | `cd ssui-vscode && yarn compile`（webpack） |
| 前端整体 | `yarn build:frontend`（根目录） | `build:components` + `build:functional_ui` |
| 完整桌面安装包 | `yarn package`（根目录） | `build:frontend` → `ext:package` → `build:desktop` |
| Python 测试 | `yarn test`（根目录） | `python tests/run_tests.py`（经 venv.cjs） |

**注意：** `desktop` 的 `yarn build` 仅验证前端 TypeScript + Vite 产物，**不包含** Tauri/Rust 编译。完整桌面应用构建用根目录 `yarn build:desktop`（`tauri build`）。

---

## 根目录 `package.json` 脚本

### 开发（dev）

| 命令 | 说明 |
|------|------|
| `yarn dev:desktop` | **最常用**。先 `build:frontend`，再 `desktop` 下 `tauri dev`。若 7422 未被占用，会自动启动 server 和 executor |
| `yarn dev:desktop_sb` | 启动 desktop Storybook（端口 6006），独立开发 React 组件 |
| `yarn dev:server` | 先 `build:frontend`，再启动 FastAPI（`python -m server --dev`，端口 **7422**） |
| `yarn dev:server:no_build` | 同上但不重新构建前端 |
| `yarn dev:executor` | 启动 SSExecutor（`python -m ss_executor`） |
| `yarn dev:functional_ui` | functional_ui Vite 开发服（端口 **7420**） |
| `yarn dev:canvas` | Image 扩展 Vite 开发服（`extensions/Image`） |
| `yarn dev:vscode` | VS Code 插件 webpack watch |

> `doc/BuildSystem.md` 提到 `yarn dev:components`，但**根 package.json 中不存在此脚本**。组件库无 `dev` 脚本，开发时修改 `ssui_components` 后需 `yarn build:components`，或依赖引用方的 dev 服务器热更新。

### 构建（build）

| 命令 | 说明 |
|------|------|
| `yarn build:frontend` | 构建 components + functional_ui |
| `yarn build:components` | 构建 `frontend/ssui_components` |
| `yarn build:functional_ui` | 构建 `frontend/functional_ui` |
| `yarn build:desktop_ui` | 仅构建 desktop 前端（`cd desktop && yarn build`） |
| `yarn build:desktop` | 构建 Tauri 桌面应用（release） |
| `yarn build:desktop:debug` | 构建 Tauri 桌面应用（debug） |
| `yarn build:example` | 构建示例扩展 |
| `yarn build:extension_builder` | 编译 `ssext` CLI |
| `yarn build:vscode` | 编译 VS Code 插件 |

### 打包（package）

| 命令 | 说明 |
|------|------|
| `yarn package` | `build:frontend` → `ext:package` → `build:desktop`，产出在 `desktop/src-tauri/target/release/bundle` |
| `yarn package:debug` | 同上，使用 debug 构建（含完整调试信息，WebView 可 F12） |
| `yarn package:vscode` | 打包 VS Code 插件 |
| `yarn ext:package` | 并行打包 Image / Video / Audio 扩展到 `desktop/src-tauri/resources/extensions/` |
| `yarn ext:package_Image` | 仅打包 Image 扩展 |

扩展打包前需先 `yarn build:extension_builder`，并在 `extension_builder` 目录执行 `npm link` 使全局可用 `ssext`（见 `doc/Package.md`）。

### 测试

| 命令 | 说明 |
|------|------|
| `yarn test` | 运行全部 Python 测试 |
| `yarn test_on <name>` | 运行指定测试，如 `yarn test_on ss_executor_test` |
| `RUN_SLOW_TESTS=1 yarn test` | 包含慢速测试（依赖大模型，发布前需跑通） |

子包内测试：

- `frontend/ssui_components`：`yarn test`（Jest）
- `extensions/Image`：`yarn test`（Jest）
- `ssui-vscode`：`yarn test`（vscode-test，会先 lint + compile）

### 依赖与环境

| 命令 | 说明 |
|------|------|
| `yarn`（根目录） | 触发 `postinstall` → `dependencies/install.cjs`，安装 JS 依赖、Python 虚拟环境（`.venv`）及 Python 包 |
| `yarn check_deps` | 检查 yarn / rustc / cargo 版本 |
| `yarn requirements` | 生成 Python 依赖文件 |
| `yarn install-requirements` | 安装 Python 依赖 |
| `yarn update-lock` | 更新依赖 lock 文件 |
| `yarn update-lock:no-upgrade` | 更新 lock 但不升级版本（添加新依赖时有用） |
| `yarn docker` / `yarn docker-run` | 构建 / 运行 Docker 镜像 |

环境变量：

- `SSUI_CI_SKIP_INSTALL=1`：跳过 `postinstall` 安装
- `NODE_ENV=production`：desktop 下 `tauri dev` 时可测试安装流程

Python 统一入口：`node dependencies/venv.cjs <命令> [参数]`，在 `.venv` 中执行。

---

## 子项目 `package.json` 脚本

### `desktop/`

| 命令 | 说明 |
|------|------|
| `yarn dev` | Vite 开发服（仅 UI，不含 Tauri） |
| `yarn build` | **`tsc && vite build`**（验证 desktop 前端改动的标准命令） |
| `yarn preview` | 预览 Vite 构建产物 |
| `yarn tauri` | Tauri CLI 透传（如 `yarn tauri dev`、`yarn tauri build`） |
| `yarn storybook` | Storybook 开发服（`-p 6006`） |
| `yarn copy-resources` | 复制 lock 文件、打包 backend/server 等到 `src-tauri/resources` |

`predev` / `prebuild` 会自动执行 `copy-resources`。

根目录等价：`yarn dev:desktop_sb` = desktop storybook；`yarn build:desktop_ui` = desktop build。

> `desktop/README.md` 写到根目录 `yarn dev:desktop_ui`，但根 package.json **无此脚本**。仅开发 UI 时在 `desktop/` 下执行 `yarn dev`；构建 UI 用 `yarn build:desktop_ui`。

### `frontend/ssui_components/`

| 命令 | 说明 |
|------|------|
| `yarn build` | `tsc && vite build` |
| `yarn fastapi` | 启动组件测试用 FastAPI 服务 |
| `yarn test` | Jest 单元测试 |

无 `dev` 脚本；被 `functional_ui`、`desktop`、`extensions/Image` 通过 workspace 依赖引用。

### `frontend/functional_ui/`

| 命令 | 说明 |
|------|------|
| `yarn dev` | Vite 开发服 |
| `yarn build` | `tsc && vite build` |
| `yarn preview` | 预览构建产物 |

### `extensions/Image/`

| 命令 | 说明 |
|------|------|
| `yarn dev` | Canvas 扩展 Vite 开发服 |
| `yarn build` | `tsc && vite build` |
| `yarn test` | Jest |

### `extensions/example/`

| 命令 | 说明 |
|------|------|
| `yarn build` | `tsc`（TypeScript 编译示例插件） |

### `extension_builder/`

| 命令 | 说明 |
|------|------|
| `yarn build` | `tsc`，产出 `ssext` CLI（`bin: ssext`） |
| `yarn start` | `node dist/index.js` |

### `ssui-vscode/`

| 命令 | 说明 |
|------|------|
| `yarn compile` | webpack 开发构建 |
| `yarn watch` | webpack watch 模式 |
| `yarn package` | webpack 生产构建（`vscode:prepublish` 也会调用） |
| `yarn lint` | ESLint |
| `yarn test` | VS Code 扩展测试 |

---

## 常用开发场景

### 1. 日常桌面开发（推荐）

```bash
yarn dev:desktop
```

### 2. 同时热更新 Functional UI

```bash
yarn dev:desktop
yarn dev:functional_ui    # 另开终端
```

desktop 检测到 **7420** 被占用时，会用 functional_ui 开发服替代内嵌的 7422 资源。

### 3. 不用桌面壳，浏览器调试 Functional UI

```bash
yarn dev:server
yarn dev:executor
yarn dev:functional_ui
```

示例 URL：`http://localhost:7420/?path=<example_path>/basic/workflow-sd1.py`

### 4. 独立开发 desktop React 组件（Storybook）

```bash
yarn dev:desktop_sb
# 或 cd desktop && yarn storybook
```

### 5. 开发 Image Canvas 扩展

```bash
yarn dev:canvas
# 或 cd extensions/Image && yarn dev
```

### 6. 开发 VS Code 插件

```bash
yarn dev:vscode
# 或 cd ssui-vscode && yarn watch
```

### 7. 手动拆分后端（便于观察日志）

```bash
yarn dev:server          # 必须先 build:frontend
yarn dev:executor        # 手动启动 server 时必须同时启动 executor
yarn dev:functional_ui
yarn dev:desktop
```

---

## 服务端口

| 端口 | 服务 |
|------|------|
| 7422 | FastAPI 应用服务器 / API 文档 `/docs` |
| 7420 | functional_ui Vite 开发服 |
| 6006 | desktop Storybook |

---

## Git Hooks

提交前代码检查（可选配置）：

```bash
git config --local core.hooksPath .githooks/
```

---

## AI 助手操作备忘

1. **验证 TypeScript/React 改动**：到**被修改包所在目录**执行 `yarn build`，不要裸跑 `npx tsc`。
2. **验证 desktop 故事/组件**：`cd desktop && yarn build` 或 `yarn dev:desktop_sb` 手动查看。
3. **修改了 ssui_components**：先 `yarn build:components`，或根目录 `yarn build:frontend`，再启动依赖它的 dev 服务。
4. **完整发布前**：`RUN_SLOW_TESTS=1 yarn test`，再按 `doc/Package.md` 执行 `yarn package`。
5. **文档与代码不一致时以 `package.json` 为准**（已知：`dev:components`、`dev:desktop_ui` 在文档/README 中出现但根 scripts 无定义）。
