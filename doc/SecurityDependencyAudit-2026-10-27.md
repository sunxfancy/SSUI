# SSUI 依赖安全调研与定向升级（2026-10-27）

## 基线与交付

独立云环境 `/workspace/SSUI`，不占用用户活跃桌面。最终基线是已显式获取的 `origin/dev` **10fdb03332615b32e4b83f4de65433f7ac84ea14**（merge #106）。main 是 fe5d443fceea6df025c4b5949c8740e51877c428。dev 是仓库开发/CI 目标，main 按 promote 发布流程更新，故选择 dev。

第一次普通 fetch 被环境保存的 main-only refspec 限制，未刷新 dev 引用，最初基线为 1ccb637e。已核对 `git ls-remote` 并用显式 refspec 获取最新 dev、解决 manifests/lockfile 冲突，保留全部新测试、Canvas 和环境配置。原安全提交 **6321615881875b2d93ce4eea8636af55dca21beb** 保留于 `security/dependency-audit-20261027-original`；最终工作在 `security/dependency-audit-20261027`。未改全局 Git 配置，未推送、建 PR、合并、部署或发布。

已读 AGENTS.md、CLAUDE.md 和最新 doc/DevelopmentEnvironments.md。JS 安装使用 `SSUI_CI_SKIP_INSTALL=1`；辅助 Python 验证使用任务专用 `.venv-security-audit`，不修改共享 venv、模型或缓存配置。没有修改 Video/Motion/3D 模型移植文件。

## 结论与实际暴露

- **受影响版本已确认，未运行恶意载荷。** 公告严重性是扫描器评级，不表示 SSUI 已存在可直接利用的远程执行链。
- Rust shell 2.2.0 的 GHSA-c9pr-q8gx-3mgp / CVE-2025-31477：插件已注册，但默认窗口 capabilities 未允许 shell open，源码未使用其 JS open。RCE 还依赖暴露该接口、恶意协议和系统处理程序。升级到 2.2.1，同时提升 JS 最低版本。
- form-data 是 desktop → axios 的 Node 适配器依赖；当前 axios 用于 WebView 模型查询 GET，没有在该路径使用 Node multipart。仍升级 axios 和相关传递包以消除锁文件中的已知漏洞。
- shell-quote 在 concurrently 开发/打包命令链；未发现不可信对象操作符输入。更新覆盖 quote 注入和 parse DoS 两类公告。
- JS tar 仅在资源/扩展打包处创建归档，未在这两处解压不可信归档。Rust tar 用于安装资源解压，因此另行修复其已知公告。
- 最新 dev 的开发/测试工具也含受影响包。定向刷新有公告的版本和必要父包，保留可用主版本；Vitest 3 的公告没有兼容补丁，升级到 4.1.12，现有桌面/工作流测试均通过。

## 具体改动（10 个文件）

| 文件 | 改动 |
|---|---|
| package.json | Vite resolution 6.3.5→6.4.5；限定路径修复 postcss/tmp/serialize-javascript/uuid/js-yaml/deepmerge-ts/basic-ftp |
| yarn.lock | 定向安全更新和必要依赖整理，完整版本表见下 |
| desktop/package.json | tar ^7.5.21，shell ^2.2.1，Vitest ^4.1.12；移除未使用 updater JS 包 |
| frontend/functional_ui/package.json | Vitest ^4.1.12 |
| extension_builder/package.json | tar 6→7，移除旧 @types/tar，使用 tar 自带类型 |
| extension_builder/src/commands/package.ts | tar 7 命名空间导入 |
| desktop/src-tauri/Cargo.toml | shell 最低 2.2.1，移除未使用的 updater，保留 window-state 原平台条件 |
| desktop/src-tauri/Cargo.lock | shell、网络/TLS/tar/plist 等受影响链路定向更新，移除 updater/zip 及无用传递包 |
| desktop/src-tauri/src/lib.rs | 删除原已注释的 updater 注册行 |
| doc/SecurityDependencyAudit-2026-10-27.md | 本报告 |

### 为什么可以移除 updater

仓库没有 updater 的 JS/Rust 调用，没有更新端点配置，lib.rs 的唯一注册行已经注释。其 Windows 分支引入 zip 2.5.0，包含 RUSTSEC-2026-0367/0368/0369；ZipArchive::extract 的使用真实存在，但当前产品未启用该功能。兼容范围内升级 updater 只能到 2.8.1 / zip 4.6.1，仍受影响。移除休眠依赖不会改变现有行为，避免为消除警报升级整套 Tauri；将来实现自动更新时应重新引入已修复且经过验证的版本。这次没有改变升级端点、签名或任何安全设置。

### 限定路径替换与兼容验证

- external-editor/tmp 0.2.7：创建、读取、清理临时文件通过。
- mocha/serialize-javascript 7.1.4：Mocha 并行 worker 测试通过。
- Storybook addon-actions/uuid 11.1.1：实际使用的 v4 + validate API 通过；保留 Storybook 8，避免整体主版本迁移。
- WDIO/deepmerge-ts 8.0.2：合并嵌套配置与数组、导入 @wdio/config 通过。
- get-uri/basic-ftp 6.2.3：通过本机临时 FTP 服务完成真实 downloadTo 下载，覆盖 get-uri 使用的接口。
- Redocly/js-yaml 4.3.2：同主版本安全替换。

这些替换只作用于对应父链；没有把所有同名包全局强制到不兼容主版本。Node 环境为 24.19，仓库 CI 为 Node 22，均满足工具链要求。完整 GUI/E2E 行为仍需要正常 CI 环境验证。

## 版本变化

| npm 包 | 原版本 | 新版本 |
|---|---|---|
| @ampproject/remapping | 2.3.0 | 移除 |
| @babel/compat-data | 7.26.8, 7.27.2 | 7.29.7 |
| @babel/core | 7.26.10, 7.27.1 | 7.29.7 |
| @babel/generator | 7.27.0, 7.27.1 | 7.27.0, 7.27.1, 7.29.8 |
| @babel/helper-compilation-targets | 7.27.0, 7.27.2 | 7.29.7 |
| @babel/helper-globals | — | 7.29.7 |
| @babel/helper-module-imports | 7.25.9, 7.27.1 | 7.29.7 |
| @babel/helper-module-transforms | 7.26.0, 7.27.1 | 7.29.7 |
| @babel/helper-string-parser | 7.25.9, 7.27.1 | 7.25.9, 7.27.1, 7.29.11 |
| @babel/helper-validator-option | 7.25.9, 7.27.1 | 7.29.7 |
| @babel/helpers | 7.27.0, 7.27.1 | 7.29.10 |
| @babel/parser | 7.27.0, 7.27.2 | 7.27.0, 7.27.2, 7.29.11 |
| @babel/template | 7.27.0, 7.27.2 | 7.27.0, 7.27.2, 7.29.7 |
| @babel/traverse | 7.27.0, 7.27.1 | 7.27.1, 7.29.10 |
| @babel/types | 7.27.0, 7.27.1 | 7.27.0, 7.27.1, 7.29.11 |
| @eslint-community/eslint-utils | 4.6.1 | 4.10.1, 4.6.1 |
| @eslint/config-array | 0.20.0 | 0.21.2 |
| @eslint/config-helpers | 0.2.1 | 0.4.2 |
| @eslint/core | 0.13.0 | 0.17.0 |
| @eslint/eslintrc | 3.3.1 | 3.3.7 |
| @eslint/js | 9.25.1 | 9.39.5 |
| @eslint/object-schema | 2.1.6 | 2.1.7 |
| @eslint/plugin-kit | 0.2.8 | 0.4.1 |
| @humanfs/core | 0.19.1 | 0.19.2 |
| @humanfs/node | 0.16.6 | 0.16.8 |
| @humanfs/types | — | 0.15.0 |
| @humanwhocodes/retry | 0.3.1, 0.4.2 | 0.4.2, 0.4.3 |
| @jridgewell/gen-mapping | 0.3.8 | 0.3.13, 0.3.8 |
| @jridgewell/remapping | — | 2.3.5 |
| @jridgewell/trace-mapping | 0.3.25 | 0.3.25, 0.3.31 |
| @napi-rs/lzma-linux-x64-gnu | — | 1.5.1 |
| @rollup/rollup-android-arm-eabi | 4.40.0 | 4.65.1 |
| @rollup/rollup-android-arm64 | 4.40.0 | 4.65.1 |
| @rollup/rollup-darwin-arm64 | 4.40.0 | 4.65.1 |
| @rollup/rollup-darwin-x64 | 4.40.0 | 4.65.1 |
| @rollup/rollup-freebsd-arm64 | 4.40.0 | 4.65.1 |
| @rollup/rollup-freebsd-x64 | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-arm-gnueabihf | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-arm-musleabihf | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-arm64-gnu | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-arm64-musl | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-loong64-gnu | — | 4.65.1 |
| @rollup/rollup-linux-loong64-musl | — | 4.65.1 |
| @rollup/rollup-linux-loongarch64-gnu | 4.40.0 | 移除 |
| @rollup/rollup-linux-powerpc64le-gnu | 4.40.0 | 移除 |
| @rollup/rollup-linux-ppc64-gnu | — | 4.65.1 |
| @rollup/rollup-linux-ppc64-musl | — | 4.65.1 |
| @rollup/rollup-linux-riscv64-gnu | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-riscv64-musl | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-s390x-gnu | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-x64-gnu | 4.40.0 | 4.65.1 |
| @rollup/rollup-linux-x64-musl | 4.40.0 | 4.65.1 |
| @rollup/rollup-openbsd-x64 | — | 4.65.1 |
| @rollup/rollup-openharmony-arm64 | — | 4.65.1 |
| @rollup/rollup-win32-arm64-msvc | 4.40.0 | 4.65.1 |
| @rollup/rollup-win32-ia32-msvc | 4.40.0 | 4.65.1 |
| @rollup/rollup-win32-x64-gnu | — | 4.65.1 |
| @rollup/rollup-win32-x64-msvc | 4.40.0 | 4.65.1 |
| @standard-schema/spec | — | 1.1.0 |
| @storybook/addon-actions | 8.6.12 | 8.6.14 |
| @storybook/addon-backgrounds | 8.6.12 | 8.6.14 |
| @storybook/addon-controls | 8.6.12 | 8.6.14 |
| @storybook/addon-docs | 8.6.12 | 8.6.14 |
| @storybook/addon-essentials | 8.6.12 | 8.6.14 |
| @storybook/addon-highlight | 8.6.12 | 8.6.14 |
| @storybook/addon-measure | 8.6.12 | 8.6.14 |
| @storybook/addon-outline | 8.6.12 | 8.6.14 |
| @storybook/addon-toolbars | 8.6.12 | 8.6.14 |
| @storybook/addon-viewport | 8.6.12 | 8.6.14 |
| @storybook/blocks | 8.6.12 | 8.6.14 |
| @storybook/builder-vite | 8.6.12 | 8.6.19 |
| @storybook/components | 8.6.12 | 8.6.19 |
| @storybook/core | 8.6.12 | 8.6.19 |
| @storybook/csf-plugin | 8.6.12 | 8.6.14, 8.6.19 |
| @storybook/icons | 1.4.0 | 1.6.0 |
| @storybook/manager-api | 8.6.12 | 8.6.19 |
| @storybook/preview-api | 8.6.12 | 8.6.19 |
| @storybook/react | 8.6.12 | 8.6.19 |
| @storybook/react-dom-shim | 8.6.12 | 8.6.14, 8.6.19 |
| @storybook/react-vite | 8.6.12 | 8.6.19 |
| @storybook/theming | 8.6.12 | 8.6.19 |
| @tauri-apps/api | 2.5.0 | 2.12.4, 2.5.0 |
| @tauri-apps/plugin-shell | 2.2.1 | 2.5.0 |
| @tauri-apps/plugin-updater | 2.7.1 | 移除 |
| @types/eslint | 9.6.1 | 移除 |
| @types/eslint-scope | 3.7.7 | 移除 |
| @types/estree | 1.0.7 | 1.0.7, 1.0.9 |
| @types/js-cookie | 2.2.7 | 3.0.6 |
| @types/tar | 6.1.13 | 移除 |
| @vitest/expect | 3.2.7 | 4.1.12 |
| @vitest/mocker | 3.2.7 | 4.1.12 |
| @vitest/pretty-format | 2.1.9, 3.2.7, 4.1.11 | 2.1.9, 4.1.11, 4.1.12 |
| @vitest/runner | 3.2.7 | 4.1.12 |
| @vitest/snapshot | 2.1.9, 3.2.7, 4.1.11 | 2.1.9, 4.1.11, 4.1.12 |
| @vitest/spy | 3.2.7 | 4.1.12 |
| @vitest/utils | 3.2.7, 4.1.11 | 4.1.11, 4.1.12 |
| acorn | 8.14.1 | 8.14.1, 8.19.0 |
| agent-base | 7.1.3 | 6.0.2, 7.1.3 |
| ajv | 6.12.6, 8.17.1 | 6.15.0, 8.20.0 |
| ajv-formats | 2.1.1 | 3.0.1 |
| axios | 1.9.0 | 1.20.0 |
| baseline-browser-mapping | — | 2.11.33 |
| basic-ftp | 5.3.1 | 6.2.3 |
| brace-expansion | 1.1.11, 2.0.1 | 1.1.21, 2.1.7 |
| browserslist | 4.24.4 | 4.29.5 |
| cac | 6.7.14 | 移除 |
| caniuse-lite | 1.0.30001715 | 1.0.30001819 |
| chai | 5.3.3 | 6.3.0 |
| check-error | 2.1.3 | 移除 |
| chownr | 2.0.0, 3.0.0 | 3.0.0 |
| deepmerge-ts | 7.1.6 | 8.0.2 |
| diff | 5.2.0, 8.0.4 | 5.2.2, 8.0.4 |
| electron-to-chromium | 1.5.143 | 1.5.465 |
| enhanced-resolve | 5.18.1 | 5.18.1, 5.26.0 |
| es-module-lexer | 1.7.0 | 2.3.2 |
| eslint | 9.25.1 | 9.39.5 |
| eslint-scope | 5.1.1, 8.3.0 | 8.4.0 |
| eslint-visitor-keys | 3.4.3, 4.2.0 | 3.4.3, 4.2.0, 4.2.1 |
| espree | 10.3.0 | 10.3.0, 10.4.0 |
| estraverse | 4.3.0, 5.3.0 | 5.3.0 |
| fast-uri | 3.0.6 | 3.1.9 |
| flatted | 3.3.3 | 3.4.4 |
| follow-redirects | 1.15.9 | 1.16.2 |
| form-data | 4.0.2 | 4.0.6 |
| fs-minipass | 2.1.0 | 移除 |
| glob | 10.4.5, 10.5.0, 7.2.3, 8.1.0 | 10.5.0, 7.2.3, 8.1.0 |
| glob-to-regexp | 0.4.1 | 移除 |
| hasown | 2.0.2 | 2.0.2, 2.0.4 |
| https-proxy-agent | 7.0.6 | 5.0.1, 7.0.6 |
| ip-address | 10.5.0 | 10.7.5 |
| js-cookie | 2.2.1 | 3.0.8 |
| js-tokens | 4.0.0, 9.0.1 | 4.0.0 |
| js-yaml | 3.14.1, 4.1.0, 4.3.1 | 3.15.2, 4.3.2 |
| loader-runner | 4.3.0 | 移除 |
| lodash | 4.17.21, 4.18.1 | 4.18.1 |
| loupe | 3.2.1 | 移除 |
| mime-db | 1.52.0 | 1.52.0, 1.54.0 |
| minimatch | 3.1.2, 3.1.5, 5.1.6, 5.1.9, 9.0.5 | 3.1.5, 5.1.9, 9.0.9 |
| minimizer-webpack-plugin | — | 5.13.1 |
| minipass | 3.3.6, 4.2.8, 5.0.0, 7.1.2 | 7.1.2 |
| minizlib | 2.1.2, 3.0.2 | 3.1.0 |
| mkdirp | 1.0.4, 3.0.1 | 移除 |
| nanoid | 3.3.11 | 3.3.20 |
| neo-async | 2.6.2 | 移除 |
| node-releases | 2.0.19 | 2.0.60 |
| obug | — | 2.2.1 |
| os-tmpdir | 1.0.2 | 移除 |
| pathval | 2.0.1 | 移除 |
| picomatch | 2.3.1, 4.0.2, 4.0.5 | 2.3.2, 4.0.7 |
| postcss | 8.4.49, 8.5.3 | 8.5.32 |
| proxy-from-env | 1.1.0 | 1.1.0, 2.1.0 |
| randombytes | 2.1.0 | 移除 |
| react-use | 17.6.0 | 17.6.1 |
| rollup | 4.40.0 | 4.65.1 |
| schema-utils | 4.3.2 | 4.8.1 |
| serialize-javascript | 6.0.2 | 7.1.4 |
| shell-quote | 1.8.2 | 1.12.0 |
| source-map-js | 1.2.1 | 1.2.2 |
| std-env | 3.10.0 | 4.3.0 |
| storybook | 8.6.12 | 8.6.19 |
| strip-literal | 3.1.0 | 移除 |
| tapable | 2.2.1 | 2.2.1, 2.3.3 |
| tar | 6.1.15, 7.4.3 | 7.5.22 |
| terser | 5.39.0 | 5.51.2 |
| terser-webpack-plugin | 5.3.14 | 移除 |
| tinyexec | 0.3.2 | 1.3.1 |
| tinypool | 1.1.1 | 移除 |
| tinyrainbow | 1.2.0, 2.0.0, 3.1.1 | 1.2.0, 3.1.1 |
| tinyspy | 4.0.4 | 移除 |
| tmp | 0.0.33 | 0.2.7 |
| undici | 6.28.0, 7.29.0 | 6.29.1, 7.30.1 |
| update-browserslist-db | 1.1.3 | 1.3.4 |
| uuid | 9.0.1 | 11.1.1 |
| vite | 6.3.5 | 6.4.5 |
| vite-node | 3.2.4 | 移除 |
| vitest | 3.2.7 | 4.1.12 |
| watchpack | 2.4.2 | 2.6.3 |
| webpack | 5.99.7 | 5.112.2 |
| webpack-sources | 3.2.3 | 3.6.0 |
| ws | 8.18.2, 8.21.3 | 8.22.0 |
| yallist | 3.1.1, 4.0.0, 5.0.0 | 3.1.1, 5.0.0 |
| yaml | 2.7.1 | 2.9.1 |

| Rust crate | 原版本 | 新版本 |
|---|---|---|
| arbitrary | 1.4.1 | 移除 |
| bytes | 1.10.1 | 1.12.1 |
| chacha20 | — | 0.10.2 |
| cpufeatures | 0.2.17 | 0.2.17, 0.3.1 |
| crossbeam-channel | 0.5.14 | 0.5.17 |
| deranged | 0.4.1 | 0.5.9 |
| derive_arbitrary | 1.4.1 | 移除 |
| getrandom | 0.1.16, 0.2.15, 0.3.2 | 0.1.16, 0.2.15, 0.3.2, 0.4.3 |
| h2 | 0.4.8 | 0.4.20 |
| lru-slab | — | 0.1.3 |
| minisign-verify | 0.2.3 | 移除 |
| num-conv | 0.1.0 | 0.2.2 |
| objc2-osa-kit | 0.3.0 | 移除 |
| osakit | 0.3.1 | 移除 |
| plist | 1.7.1 | 1.10.0 |
| quick-xml | 0.32.0 | 0.41.0 |
| quinn-proto | 0.11.10 | 0.11.19 |
| r-efi | 5.2.0 | 5.2.0, 6.0.0 |
| rand | 0.7.3, 0.8.5, 0.9.1 | 0.10.3, 0.7.3, 0.8.5, 0.9.1 |
| rand_core | 0.5.1, 0.6.4, 0.9.3 | 0.10.1, 0.5.1, 0.6.4, 0.9.3 |
| rand_pcg | 0.2.1 | 0.10.2, 0.2.1 |
| rustls | 0.23.25 | 0.23.46 |
| rustls-pki-types | 1.11.0 | 1.15.1 |
| rustls-webpki | 0.103.1 | 0.103.16 |
| serde | 1.0.219 | 1.0.229 |
| serde_core | — | 1.0.229 |
| serde_derive | 1.0.219 | 1.0.229 |
| syn | 1.0.109, 2.0.119 | 1.0.109, 2.0.119, 3.0.9 |
| tar | 0.4.44 | 0.4.46 |
| tauri-plugin-shell | 2.2.0 | 2.2.1 |
| tauri-plugin-updater | 2.6.1 | 移除 |
| time | 0.3.41 | 0.3.55 |
| time-core | 0.1.4 | 0.1.9 |
| time-macros | 0.2.22 | 0.2.32 |
| webpki-roots | 0.26.8 | 0.26.11, 1.0.11 |
| zip | 2.5.0 | 移除 |

## 公告明细

以下为原受影响包的全部 npm 公告 ID，以及 Rust 公告；与最终残余列表对照，未列为残余的已通过升级或移除依赖消除。

### npm 公告（按包分组；未列为残余者均已移除受影响版本）

- @babel/core: [GHSA-4x5r-pxfx-6jf8](https://github.com/advisories/GHSA-4x5r-pxfx-6jf8)
- @eslint/plugin-kit: [GHSA-xffm-g5w8-qvg7](https://github.com/advisories/GHSA-xffm-g5w8-qvg7)
- @humanfs/node: [GHSA-p498-v437-472g](https://github.com/advisories/GHSA-p498-v437-472g)
- @storybook/core: [GHSA-f2ph-cmg5-wxc8](https://github.com/advisories/GHSA-f2ph-cmg5-wxc8), [GHSA-px85-f4q5-jh77](https://github.com/advisories/GHSA-px85-f4q5-jh77)
- @vitest/mocker: [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9), [GHSA-qxg6-89mg-rqv8](https://github.com/advisories/GHSA-qxg6-89mg-rqv8)
- ajv: [GHSA-2g4f-4pwh-qvx6](https://github.com/advisories/GHSA-2g4f-4pwh-qvx6)
- axios: [GHSA-35jp-ww65-95wh](https://github.com/advisories/GHSA-35jp-ww65-95wh), [GHSA-3g43-6gmg-66jw](https://github.com/advisories/GHSA-3g43-6gmg-66jw), [GHSA-3p68-rc4w-qgx5](https://github.com/advisories/GHSA-3p68-rc4w-qgx5), [GHSA-3w6x-2g7m-8v23](https://github.com/advisories/GHSA-3w6x-2g7m-8v23), [GHSA-42h9-826w-cgv3](https://github.com/advisories/GHSA-42h9-826w-cgv3), [GHSA-43fc-jf86-j433](https://github.com/advisories/GHSA-43fc-jf86-j433), [GHSA-445q-vr5w-6q77](https://github.com/advisories/GHSA-445q-vr5w-6q77), [GHSA-4hjh-wcwx-xvwj](https://github.com/advisories/GHSA-4hjh-wcwx-xvwj), [GHSA-5c9x-8gcm-mpgx](https://github.com/advisories/GHSA-5c9x-8gcm-mpgx), [GHSA-62hf-57xw-28j9](https://github.com/advisories/GHSA-62hf-57xw-28j9), [GHSA-6chq-wfr3-2hj9](https://github.com/advisories/GHSA-6chq-wfr3-2hj9), [GHSA-777c-7fjr-54vf](https://github.com/advisories/GHSA-777c-7fjr-54vf), [GHSA-7q8q-rj6j-mhjq](https://github.com/advisories/GHSA-7q8q-rj6j-mhjq), [GHSA-898c-q2cr-xwhg](https://github.com/advisories/GHSA-898c-q2cr-xwhg), [GHSA-9fr6-4gfg-395g](https://github.com/advisories/GHSA-9fr6-4gfg-395g), [GHSA-fvcv-3m26-pcqx](https://github.com/advisories/GHSA-fvcv-3m26-pcqx), [GHSA-hfxv-24rg-xrqf](https://github.com/advisories/GHSA-hfxv-24rg-xrqf), [GHSA-j5f8-grm9-p9fc](https://github.com/advisories/GHSA-j5f8-grm9-p9fc), [GHSA-j8rh-479h-cp32](https://github.com/advisories/GHSA-j8rh-479h-cp32), [GHSA-jqh4-m9w3-8hp9](https://github.com/advisories/GHSA-jqh4-m9w3-8hp9), [GHSA-m7pr-hjqh-92cm](https://github.com/advisories/GHSA-m7pr-hjqh-92cm), [GHSA-mmx7-hfxf-jppx](https://github.com/advisories/GHSA-mmx7-hfxf-jppx), [GHSA-p92q-9vqr-4j8v](https://github.com/advisories/GHSA-p92q-9vqr-4j8v), [GHSA-pf86-5x62-jrwf](https://github.com/advisories/GHSA-pf86-5x62-jrwf), [GHSA-pmv8-rq9r-6j72](https://github.com/advisories/GHSA-pmv8-rq9r-6j72), [GHSA-pmwg-cvhr-8vh7](https://github.com/advisories/GHSA-pmwg-cvhr-8vh7), [GHSA-q8qp-cvcw-x6jj](https://github.com/advisories/GHSA-q8qp-cvcw-x6jj), [GHSA-vf2m-468p-8v99](https://github.com/advisories/GHSA-vf2m-468p-8v99), [GHSA-vh66-26gq-q6x8](https://github.com/advisories/GHSA-vh66-26gq-q6x8), [GHSA-w9j2-pvgh-6h63](https://github.com/advisories/GHSA-w9j2-pvgh-6h63), [GHSA-xhjh-pmcv-23jw](https://github.com/advisories/GHSA-xhjh-pmcv-23jw), [GHSA-xx6v-rp6x-q39c](https://github.com/advisories/GHSA-xx6v-rp6x-q39c)
- basic-ftp: [GHSA-c475-qrg2-pj4r](https://github.com/advisories/GHSA-c475-qrg2-pj4r)
- brace-expansion: [GHSA-3jxr-9vmj-r5cp](https://github.com/advisories/GHSA-3jxr-9vmj-r5cp), [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p), [GHSA-f886-m6hf-6m8v](https://github.com/advisories/GHSA-f886-m6hf-6m8v), [GHSA-mh99-v99m-4gvg](https://github.com/advisories/GHSA-mh99-v99m-4gvg), [GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr), [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7), [GHSA-rgw5-rvv9-x895](https://github.com/advisories/GHSA-rgw5-rvv9-x895), [GHSA-v6h2-p8h4-qcjw](https://github.com/advisories/GHSA-v6h2-p8h4-qcjw)
- browserslist: [GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g), [GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx)
- deepmerge-ts: [GHSA-ggr8-5vv4-36mx](https://github.com/advisories/GHSA-ggr8-5vv4-36mx)
- diff: [GHSA-73rr-hh4g-fpgx](https://github.com/advisories/GHSA-73rr-hh4g-fpgx)
- extract-zip: [GHSA-7pqw-9j4j-h8q3](https://github.com/advisories/GHSA-7pqw-9j4j-h8q3), [GHSA-jmr9-qjv8-65gv](https://github.com/advisories/GHSA-jmr9-qjv8-65gv)
- fast-uri: [GHSA-333x-w4r6-6crp](https://github.com/advisories/GHSA-333x-w4r6-6crp), [GHSA-4c8g-83qw-93j6](https://github.com/advisories/GHSA-4c8g-83qw-93j6), [GHSA-7p8r-x3mc-p8w7](https://github.com/advisories/GHSA-7p8r-x3mc-p8w7), [GHSA-f65p-4m7j-42xc](https://github.com/advisories/GHSA-f65p-4m7j-42xc), [GHSA-hrr3-gc8f-f4qj](https://github.com/advisories/GHSA-hrr3-gc8f-f4qj), [GHSA-jqff-g426-hqxp](https://github.com/advisories/GHSA-jqff-g426-hqxp), [GHSA-q3j6-qgpj-74h6](https://github.com/advisories/GHSA-q3j6-qgpj-74h6), [GHSA-qw65-cvwx-89v3](https://github.com/advisories/GHSA-qw65-cvwx-89v3), [GHSA-v2hh-gcrm-f6hx](https://github.com/advisories/GHSA-v2hh-gcrm-f6hx), [GHSA-v39h-62p7-jpjc](https://github.com/advisories/GHSA-v39h-62p7-jpjc), [GHSA-w74x-v6f9-j3xg](https://github.com/advisories/GHSA-w74x-v6f9-j3xg), [GHSA-xhq7-xmqj-769h](https://github.com/advisories/GHSA-xhq7-xmqj-769h)
- flatted: [GHSA-25h7-pfq9-p65f](https://github.com/advisories/GHSA-25h7-pfq9-p65f), [GHSA-rf6f-7fwh-wjgh](https://github.com/advisories/GHSA-rf6f-7fwh-wjgh)
- follow-redirects: [GHSA-r4q5-vmmm-2653](https://github.com/advisories/GHSA-r4q5-vmmm-2653)
- form-data: [GHSA-fjxv-7rqg-78g4](https://github.com/advisories/GHSA-fjxv-7rqg-78g4), [GHSA-hmw2-7cc7-3qxx](https://github.com/advisories/GHSA-hmw2-7cc7-3qxx)
- glob: [GHSA-5j98-mcp5-4vw2](https://github.com/advisories/GHSA-5j98-mcp5-4vw2)
- ip-address: [GHSA-2vr4-cq9g-pvrc](https://github.com/advisories/GHSA-2vr4-cq9g-pvrc), [GHSA-h3mg-xc3c-68pw](https://github.com/advisories/GHSA-h3mg-xc3c-68pw), [GHSA-j6r3-76f7-8jcv](https://github.com/advisories/GHSA-j6r3-76f7-8jcv), [GHSA-rpw4-54j3-4h4q](https://github.com/advisories/GHSA-rpw4-54j3-4h4q), [GHSA-rxp7-6hxx-x8q5](https://github.com/advisories/GHSA-rxp7-6hxx-x8q5)
- js-cookie: [GHSA-qjx8-664m-686j](https://github.com/advisories/GHSA-qjx8-664m-686j)
- js-yaml: [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh), [GHSA-52cp-r559-cp3m](https://github.com/advisories/GHSA-52cp-r559-cp3m), [GHSA-5p4m-2wfm-xmqj](https://github.com/advisories/GHSA-5p4m-2wfm-xmqj), [GHSA-h67p-54hq-rp68](https://github.com/advisories/GHSA-h67p-54hq-rp68), [GHSA-mh29-5h37-fv8m](https://github.com/advisories/GHSA-mh29-5h37-fv8m)
- lodash: [GHSA-f23m-r3pf-42rh](https://github.com/advisories/GHSA-f23m-r3pf-42rh), [GHSA-r5fr-rjxr-66jc](https://github.com/advisories/GHSA-r5fr-rjxr-66jc), [GHSA-xxjr-mmjv-4gpg](https://github.com/advisories/GHSA-xxjr-mmjv-4gpg)
- minimatch: [GHSA-23c5-xmqv-rm74](https://github.com/advisories/GHSA-23c5-xmqv-rm74), [GHSA-3ppc-4f35-3m26](https://github.com/advisories/GHSA-3ppc-4f35-3m26), [GHSA-7r86-cg39-jmmj](https://github.com/advisories/GHSA-7r86-cg39-jmmj)
- nanoid: [GHSA-28wg-ghj8-5hjv](https://github.com/advisories/GHSA-28wg-ghj8-5hjv), [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8), [GHSA-xwg4-73v4-xw9w](https://github.com/advisories/GHSA-xwg4-73v4-xw9w)
- picomatch: [GHSA-3v7f-55p6-f55p](https://github.com/advisories/GHSA-3v7f-55p6-f55p), [GHSA-c2c7-rcm5-vvqj](https://github.com/advisories/GHSA-c2c7-rcm5-vvqj)
- postcss: [GHSA-6g55-p6wh-862q](https://github.com/advisories/GHSA-6g55-p6wh-862q), [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp), [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93), [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849)
- rollup: [GHSA-mw96-cpmx-2vgc](https://github.com/advisories/GHSA-mw96-cpmx-2vgc)
- serialize-javascript: [GHSA-5c6j-r48x-rmvq](https://github.com/advisories/GHSA-5c6j-r48x-rmvq), [GHSA-m5mm-p8h7-m29v](https://github.com/advisories/GHSA-m5mm-p8h7-m29v), [GHSA-qj8w-gfj5-8c6v](https://github.com/advisories/GHSA-qj8w-gfj5-8c6v)
- shell-quote: [GHSA-395f-4hp3-45gv](https://github.com/advisories/GHSA-395f-4hp3-45gv), [GHSA-w7jw-789q-3m8p](https://github.com/advisories/GHSA-w7jw-789q-3m8p)
- source-map-js: [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
- storybook: [GHSA-8452-54wp-rmv6](https://github.com/advisories/GHSA-8452-54wp-rmv6), [GHSA-f2ph-cmg5-wxc8](https://github.com/advisories/GHSA-f2ph-cmg5-wxc8), [GHSA-mjf5-7g4m-gx5w](https://github.com/advisories/GHSA-mjf5-7g4m-gx5w), [GHSA-px85-f4q5-jh77](https://github.com/advisories/GHSA-px85-f4q5-jh77)
- tar: [GHSA-23hp-3jrh-7fpw](https://github.com/advisories/GHSA-23hp-3jrh-7fpw), [GHSA-34x7-hfp2-rc4v](https://github.com/advisories/GHSA-34x7-hfp2-rc4v), [GHSA-83g3-92jg-28cx](https://github.com/advisories/GHSA-83g3-92jg-28cx), [GHSA-8qq5-rm4j-mr97](https://github.com/advisories/GHSA-8qq5-rm4j-mr97), [GHSA-8x88-c5mf-7j5w](https://github.com/advisories/GHSA-8x88-c5mf-7j5w), [GHSA-9ppj-qmqm-q256](https://github.com/advisories/GHSA-9ppj-qmqm-q256), [GHSA-f5x3-32g6-xq36](https://github.com/advisories/GHSA-f5x3-32g6-xq36), [GHSA-gvwx-54wh-qm9j](https://github.com/advisories/GHSA-gvwx-54wh-qm9j), [GHSA-qffp-2rhf-9h96](https://github.com/advisories/GHSA-qffp-2rhf-9h96), [GHSA-r292-9mhp-454m](https://github.com/advisories/GHSA-r292-9mhp-454m), [GHSA-r6q2-hw4h-h46w](https://github.com/advisories/GHSA-r6q2-hw4h-h46w), [GHSA-vmf3-w455-68vh](https://github.com/advisories/GHSA-vmf3-w455-68vh), [GHSA-w8wr-v893-vjvp](https://github.com/advisories/GHSA-w8wr-v893-vjvp)
- tinypool: [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3), [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr)
- tmp: [GHSA-52f5-9888-hmc6](https://github.com/advisories/GHSA-52f5-9888-hmc6), [GHSA-ph9p-34f9-6g65](https://github.com/advisories/GHSA-ph9p-34f9-6g65)
- undici: [GHSA-2gqq-gqf2-x968](https://github.com/advisories/GHSA-2gqq-gqf2-x968), [GHSA-2jfj-6hjv-fm6j](https://github.com/advisories/GHSA-2jfj-6hjv-fm6j), [GHSA-3wwx-pv8p-q78v](https://github.com/advisories/GHSA-3wwx-pv8p-q78v), [GHSA-3xpg-4rpp-hhhm](https://github.com/advisories/GHSA-3xpg-4rpp-hhhm), [GHSA-4qv8-2p9j-2685](https://github.com/advisories/GHSA-4qv8-2p9j-2685), [GHSA-8436-99hf-9mmv](https://github.com/advisories/GHSA-8436-99hf-9mmv), [GHSA-f72v-6w45-q472](https://github.com/advisories/GHSA-f72v-6w45-q472), [GHSA-pmjh-fq2x-6v4x](https://github.com/advisories/GHSA-pmjh-fq2x-6v4x), [GHSA-r53p-7pc4-xj5r](https://github.com/advisories/GHSA-r53p-7pc4-xj5r), [GHSA-rfgv-xxqx-mfg5](https://github.com/advisories/GHSA-rfgv-xxqx-mfg5), [GHSA-rx4f-c7p8-82vq](https://github.com/advisories/GHSA-rx4f-c7p8-82vq), [GHSA-w293-vg96-wgc3](https://github.com/advisories/GHSA-w293-vg96-wgc3), [GHSA-xjj6-f33q-929c](https://github.com/advisories/GHSA-xjj6-f33q-929c)
- uuid: [GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq)
- vite: [GHSA-4w7w-66w2-5vf9](https://github.com/advisories/GHSA-4w7w-66w2-5vf9), [GHSA-587h-7wmj-h5pm](https://github.com/advisories/GHSA-587h-7wmj-h5pm), [GHSA-698v-4r3x-3vcv](https://github.com/advisories/GHSA-698v-4r3x-3vcv), [GHSA-93m4-6634-74q7](https://github.com/advisories/GHSA-93m4-6634-74q7), [GHSA-9jrq-w75r-8gcw](https://github.com/advisories/GHSA-9jrq-w75r-8gcw), [GHSA-fx2h-pf6j-xcff](https://github.com/advisories/GHSA-fx2h-pf6j-xcff), [GHSA-g4jq-h2w9-997c](https://github.com/advisories/GHSA-g4jq-h2w9-997c), [GHSA-jqfw-vq24-v9c3](https://github.com/advisories/GHSA-jqfw-vq24-v9c3), [GHSA-p9ff-h696-f583](https://github.com/advisories/GHSA-p9ff-h696-f583), [GHSA-r825-w8mm-5pxw](https://github.com/advisories/GHSA-r825-w8mm-5pxw), [GHSA-rq7h-c2jc-7f22](https://github.com/advisories/GHSA-rq7h-c2jc-7f22), [GHSA-v6wh-96g9-6wx3](https://github.com/advisories/GHSA-v6wh-96g9-6wx3)
- vitest: [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)
- webpack: [GHSA-38r7-794h-5758](https://github.com/advisories/GHSA-38r7-794h-5758), [GHSA-8fgc-7cc6-rx7x](https://github.com/advisories/GHSA-8fgc-7cc6-rx7x)
- ws: [GHSA-58qx-3vcg-4xpx](https://github.com/advisories/GHSA-58qx-3vcg-4xpx), [GHSA-96hv-2xvq-fx4p](https://github.com/advisories/GHSA-96hv-2xvq-fx4p)
- yaml: [GHSA-48c2-rrv3-qjmp](https://github.com/advisories/GHSA-48c2-rrv3-qjmp)

### Rust 公告

- shell：GHSA-c9pr-q8gx-3mgp / CVE-2025-31477，2.2.0 → 2.2.1。
- [RUSTSEC-2026-0007](https://rustsec.org/advisories/RUSTSEC-2026-0007.html)：bytes 1.10.1 — Integer overflow in `BytesMut::reserve`
- [RUSTSEC-2025-0024](https://rustsec.org/advisories/RUSTSEC-2025-0024.html)：crossbeam-channel 0.5.14 — crossbeam-channel: double free on Drop
- [RUSTSEC-2026-0258](https://rustsec.org/advisories/RUSTSEC-2026-0258.html)：h2 0.4.8 — h2 unbounded empty DATA frames
- [RUSTSEC-2026-0195](https://rustsec.org/advisories/RUSTSEC-2026-0195.html)：quick-xml 0.32.0 — Unbounded namespace-declaration allocation in `NsReader` enables memory-exhaustion denial of service
- [RUSTSEC-2026-0194](https://rustsec.org/advisories/RUSTSEC-2026-0194.html)：quick-xml 0.32.0 — Quadratic run time when checking a start tag for duplicate attribute names
- [RUSTSEC-2026-0037](https://rustsec.org/advisories/RUSTSEC-2026-0037.html)：quinn-proto 0.11.10 — Denial of service in Quinn endpoints
- [RUSTSEC-2026-0340](https://rustsec.org/advisories/RUSTSEC-2026-0340.html)：quinn-proto 0.11.10 — Peer minimum ACK delay can panic quinn-proto when ACK_FREQUENCY transmission is enabled
- [RUSTSEC-2026-0339](https://rustsec.org/advisories/RUSTSEC-2026-0339.html)：quinn-proto 0.11.10 — Unbounded growth of pending connection ID retirements in quinn-proto
- [RUSTSEC-2026-0185](https://rustsec.org/advisories/RUSTSEC-2026-0185.html)：quinn-proto 0.11.10 —  Remote memory exhaustion in quinn-proto from unbounded out-of-order stream reassembly
- [RUSTSEC-2026-0338](https://rustsec.org/advisories/RUSTSEC-2026-0338.html)：quinn-proto 0.11.10 — Remote peer can panic quinn-proto with zero-length STREAM frames during unordered reads
- [RUSTSEC-2026-0342](https://rustsec.org/advisories/RUSTSEC-2026-0342.html)：quinn-proto 0.11.10 — Zero-length DATAGRAM frames bypass the receive buffer limit in quinn-proto
- [RUSTSEC-2026-0285](https://rustsec.org/advisories/RUSTSEC-2026-0285.html)：rustls 0.23.25 — TLS 1.3 handshake messages incorrectly accepted across encryption level boundaries
- [RUSTSEC-2026-0346](https://rustsec.org/advisories/RUSTSEC-2026-0346.html)：rustls 0.23.25 — `Debug` impls for client session values expose TLS secrets
- [RUSTSEC-2026-0349](https://rustsec.org/advisories/RUSTSEC-2026-0349.html)：rustls 0.23.25 — Unauthenticated ServerHello can downgrade later connections to classical key exchange
- [RUSTSEC-2026-0348](https://rustsec.org/advisories/RUSTSEC-2026-0348.html)：rustls 0.23.25 — Brotli certificate decompression can allocate up to 1 GiB before authentication
- [RUSTSEC-2026-0382](https://rustsec.org/advisories/RUSTSEC-2026-0382.html)：rustls-webpki 0.103.1 — Certificate verification may accept distrusted intermediates
- [RUSTSEC-2026-0049](https://rustsec.org/advisories/RUSTSEC-2026-0049.html)：rustls-webpki 0.103.1 — CRLs not considered authoritative by Distribution Point due to faulty matching logic
- [RUSTSEC-2026-0098](https://rustsec.org/advisories/RUSTSEC-2026-0098.html)：rustls-webpki 0.103.1 — Name constraints for URI names were incorrectly accepted
- [RUSTSEC-2026-0104](https://rustsec.org/advisories/RUSTSEC-2026-0104.html)：rustls-webpki 0.103.1 — Reachable panic in certificate revocation list parsing
- [RUSTSEC-2026-0099](https://rustsec.org/advisories/RUSTSEC-2026-0099.html)：rustls-webpki 0.103.1 — Name constraints were accepted for certificates asserting a wildcard name
- [RUSTSEC-2026-0068](https://rustsec.org/advisories/RUSTSEC-2026-0068.html)：tar 0.4.44 — tar-rs incorrectly ignores PAX size headers if header size is nonzero
- [RUSTSEC-2026-0067](https://rustsec.org/advisories/RUSTSEC-2026-0067.html)：tar 0.4.44 — `unpack_in` can chmod arbitrary directories by following symlinks
- [RUSTSEC-2026-0009](https://rustsec.org/advisories/RUSTSEC-2026-0009.html)：time 0.3.41 — Denial of Service via Stack Exhaustion
- [RUSTSEC-2026-0381](https://rustsec.org/advisories/RUSTSEC-2026-0381.html)：webpki-roots 0.26.8 — Bundled root certificates allow trust in distrusted emSign intermediates
- [RUSTSEC-2026-0368](https://rustsec.org/advisories/RUSTSEC-2026-0368.html)：zip 2.5.0 — zip: `ZipArchive::extract` creates symbolic links whose attacker-controlled targets are outside the destination directory
- [RUSTSEC-2026-0367](https://rustsec.org/advisories/RUSTSEC-2026-0367.html)：zip 2.5.0 —  Insecure Preservation of SUID/SGID Bits during ZIP Extraction Leading to Potential Privilege Escalation
- [RUSTSEC-2026-0369](https://rustsec.org/advisories/RUSTSEC-2026-0369.html)：zip 2.5.0 — ZipStreamReader::extract() and ZipArchive::extract() apply Unix permissions through symlinks without confining the target

## 审计结果与残余发现

- npm 官方 bulk API 对整份 yarn.lock：**186 条受影响版本范围记录 / 156 个唯一 GHSA → 2 条 / 2 个 GHSA**。修复覆盖生产和开发依赖；数量不是风险评分。
- Yarn Classic 最终 audit 返回 **10 个 high 路径记录**，均是同一 extract-zip 包的两项公告在 WDIO 中的 5 条重复路径。它仅涵盖约 945 个依赖，完整锁文件另行检查；不能把路径数当成唯一漏洞数。审计时出现 deepmerge-ts 原范围不兼容提示，已核对实际安装与锁文件中的覆盖版本并做调用验证。
- desktop Cargo.lock：shell 公告另计；首次 shell 修复后剩 27 条 RustSec，最终 **0 条已知漏洞**；保留原有 **12 unmaintained / 8 unsound / 0 yanked** 提示，含 GTK 生态等上游维护状态，未扩大为框架迁移。
- 新 Canvas Cargo.lock：cargo-audit **0 条已知漏洞**，1 个 unmaintained 提示；未改其锁文件。

唯一残余包：**extract-zip 2.0.1**，公告 [GHSA-jmr9-qjv8-65gv](https://github.com/advisories/GHSA-jmr9-qjv8-65gv)、[GHSA-7pqw-9j4j-h8q3](https://github.com/advisories/GHSA-7pqw-9j4j-h8q3)，扫描评级 high。路径：root WDIO → @wdio/utils → @puppeteer/browsers → extract-zip。它用于浏览器驱动/浏览器下载解包的开发工具，不在桌面生产资源打包链中。npm 官方注册表当前最新仍是 2.0.1，没有可升级的修复版本。需要不可信/被篡改归档等触发条件，未进行攻击验证。

**暂缓理由：** 无可用补丁；强制替换为另一解包库需要改变上游调用或维护 fork，超出此次定向更新。已升级可用的父链，保留当前 WDIO 测试功能；建议由上游发布修复后再更新，运行下载型 E2E 时继续使用可信下载源。没有为追求零告警删除现有测试体系或改变下载安全设置。

## 最新基线上的验证

| 检查 | 结果 |
|---|---|
| yarn install --frozen-lockfile --ignore-scripts | 通过；有原 peer dependency 和限定跨版本 resolution 提示 |
| build:components / build:functional_ui / build:desktop_ui | 通过，含 TypeScript、Vite 和 tar 资源归档 |
| build:vscode / build:extension_builder | 通过 |
| test:desktop_ui（Vitest 4.1.12） | 1 项通过 |
| test:functional_ui（Vitest 4.1.12） | 6 项通过 |
| test:components | 8 suites / 22 项通过；先前缺任务 venv 的尝试失败，安装任务独立最小测试环境后通过 |
| test:canvas | 5 suites / 18 项通过 |
| test:dev-config | 5 项通过，验证最新环境配置 |
| test:storybook | 3 项通过 |
| release.py 单元测试 / check-versions | 46 项通过 / required 版本一致；原非 required 包差异告警 |
| ssext tar 7 打包、临时文件、Mocha 并行、UUID、WDIO、FTP 冒烟 | 通过 |
| Canvas WASM release --no-opt | 通过，未发布任何包 |
| Image TypeScript/Vite（WASM --no-opt 产物） | 通过；正常 prebuild 的 wasm-opt 下载失败，无优化构建不代表完整优化发布验证 |
| 默认 build:canvas | 未通过：Binaryen wasm-opt v117 下载失败；WASM 编译和 wasm-bindgen 已通过。随后用脚本已有 --no-opt 参数生成验证产物。临时 prebuild 参数修改在 finally 中恢复，没有提交 |
| build:storybook | 未通过：Storybook 需写 /home/agent/.storybook/settings.json，用户目录只读/不存在；即使禁用 telemetry 仍触发全局设置写入。未扩大权限 |
| desktop cargo check --locked | 未通过：glib-2.0.pc 缺失，GTK/WebKit 也未安装；没有完成桌面 Rust 类型/链接验证 |
| git diff --check | 通过 |
| Python 模型、完整安装包、Windows/macOS、GUI/E2E | 未运行；没有安装 Torch/模型，未开启跨平台发布流程 |

构建保留既有 peer dependency / 大 chunk 警告。没有修改共享 Python 环境。原先在旧基线上的通过结果没有用于替代上述最新基线验证。

## 证据、访问限制与交付边界

完整 npm/Rust 审计 JSON、依赖树、版本与验证日志保存在独立环境 `/workspace/scratch/ssui-security-audit-20261027/`；最新执行日志使用 `ssui-latest-*` 名称。全锁文件来源：`https://registry.npmjs.org/-/npm/v1/security/advisories/bulk`；RustSec 数据由 cargo-audit 0.22.2 获取。所有公告以本次查询结果为准。

早前辅助请求 `https://crates.io/api/v1/crates/tauri-plugin-updater/2.10.0/dependencies` 返回 HTTP 403，未重试或绕过。默认 Canvas 构建的 Binaryen 下载失败，未从其他来源绕过下载；仅运行可选 --no-opt 验证。Storybook 和 Rust 桌面构建的环境障碍如上，均未申请更高权限或绕过访问限制。没有审批拒绝、待审批、推送、PR、合并或发布动作。
