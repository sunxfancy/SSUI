# 扩展构建器

此包提供 `ssext` 命令行工具。`src/index.ts` 注册 `new`（交互式创建扩展）、`init`（在当前目录初始化）和 `package`（将当前扩展打成 tar.gz）。`package` 要求当前目录有 `ssextension.yaml`，可用 `-o, --output <目录>` 指定输出位置。若扩展有 `package.json`，工具会运行其 `package` 脚本，或退回运行 `build` 脚本。

在本目录运行 `yarn build` 编译 TypeScript；仓库根目录的等价命令是 `yarn build:extension_builder`。打包现有扩展的命令与 `ssext` 配置见 [打包指南](../doc/Package.md)，清单与目录约定见 [扩展指南](../doc/Extensions.md)。
