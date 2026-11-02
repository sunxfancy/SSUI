项目打包发布
===============

## Linux 打包

```bash
yarn package:linux
# 调试包：yarn package:debug
```

Linux 默认只生成 AppImage，产物位于 `desktop/src-tauri/target/{debug/release}/bundle/appimage/`。
Tauri 自动加载 `desktop/src-tauri/tauri.linux.conf.json`，不同 CPU 架构需要分别构建。
运行时先执行 `chmod +x <文件名>.AppImage`，再直接启动该文件。

## 发布

发布采用六个原生桌面目标：Windows、macOS、Linux × x86_64 / ARM64。
版本必须先通过 PR 准备，tag 不可移动；六目标构建与独立安装验证通过后，
上传候选产物并创建发布 PR。合入 main 后，单独运行晋升工作流发布相同产物。

操作步骤、仓库配置、失败恢复及当前 ARM64 依赖阻塞见 [桌面发布指南](Release.md)。
