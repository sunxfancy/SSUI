项目打包发布
===============

## 发布前测试

项目发布release版本前，需要通过所有测试，包括slow test cases：

```bash
RUN_SLOW_TESTS=1 yarn test
```


## 打包流程

请安装如下流程进行打包：

1. 编译并link打包用命令行工具

```bash
yarn build:extension_builder
cd extension_builder && npm link   # 这会将ssext命令行工具link到全局工具
```

2. 打包所有插件

```bash
yarn ext:package
```

3. 打包项目

有两个打包版本，请根据需要选择：

```bash
yarn package
yarn package:debug # 调试版本，会包含完整的调试信息, 网页端也可以启动f12调试
```

打包好的文件在`desktop/src-tauri/target/{debug/release}/bundle`目录下。

## 发布

发布流程由 CI 自动完成（`release.yml`，与 EVEngine 相同的发布体系）：

1. 先在本地跑通全部测试（含慢速用例）：

```bash
RUN_SLOW_TESTS=1 yarn test
```

2. 在 GitHub 上从 `dev` 分支创建 **Pre-release**，tag 形如 `0.1.2`（`v` 前缀可选，如 `v0.1.2`）。
3. `release.yml` 自动执行：
   - `start`：改写 `desktop/src-tauri/Cargo.toml` 与 `desktop/package.json` 为官方版本，移动 tag，推送 `v0.1.2` 分支；
   - 严格测试：复用 `ci.yml` 在 `v0.1.2` 上跑三平台构建 + 测试；
   - 打包：Windows（MSI/NSIS）与 macOS（DMG）；
   - 冒烟测试：直接运行 release 二进制确认进程存活；Windows 静默安装 NSIS 后运行安装产物，macOS 挂载 DMG 后运行 `.app`；
   - 上传安装包到该 release；
   - `finish`：`gh release edit --prerelease=false` 转为正式发布，并打开 `promote/v0.1.2` → `main` 与 `rebase/v0.1.2` → `dev` 两个 PR。
4. 合并 `promote/v0.1.2` PR（main-gate 自动放行）更新 `main`；合并 `rebase/v0.1.2` PR 使 `dev` 包含发布改动。

冒烟测试脚本：`node scripts/smoke_app.cjs <可执行文件> [秒数]`。

> 只有冒烟测试通过后 `finish` 才会执行，release 才会从 Pre-release 转为正式，因此打包产物无法执行的版本不会成为正式发布。



