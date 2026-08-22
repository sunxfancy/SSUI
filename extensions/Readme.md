This path contains a list of extensions for the SSUI.

## 扩展目录结构约定

每个扩展统一使用以下布局：

```text
extensions/<Name>/
├── extension.py        # 可选：FastAPI APIRouter 入口（server.main 指向它）
├── ssextension.yaml    # 扩展清单：名称、版本、server/web_ui 配置
├── ssui_<name>/        # 扩展提供的 SSUI SDK Python 包（会被沙盒动态放行）
├── vendor/             # 第三方 vendored 代码（cosyvoice/matcha/trellis/stdgen 等）
└── <web>/              # 可选：扩展 Web UI 源码（如 Image 的 canvas/）
```

`ssextension.yaml` 中 `server.packages` 声明扩展提供的 SDK 包名，
沙盒加载脚本时会自动放行这些包。

