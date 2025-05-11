Stable Scripts UI
====================

![quicktest](https://github.com/sunxfancy/SSUI/actions/workflows/quicktest.yml/badge.svg) [English Readme](Readme.md)

Stable Scripts UI 是一个基于网页的用户界面，用于 `Stable Scripts` - 一种可以被其他用户轻松复现相同结果的 Python 脚本。


![Desktop Version](doc/images/presentation.png)
![VSCode Plugin](doc/images/vscode-plugin.png)


## 为什么选择 Stable Scripts？

与其他稳定扩散 UI 相比，SSUI 有 5 个主要优势：

- **易于使用**：快速创建、运行和分享稳定脚本，这些脚本是自包含的，可以自动下载必要的 Python 模块、AI 模型和其他依赖数据。
- **可复现**：脚本、依赖的模块和 SSUI 本身都是标记版本的。脚本可以在与脚本作者完全相同的环境中运行。
- **管理功能**：轻松管理您的模型和配置，方便地从Civitai和HuggingFace下载模型。
- **强类型**：所有资源（包括模型）都是强类型的，可以防止被误用。
- **可定制**：您可以自定义脚本、类型，并通过插件扩展支持的模型、面板、加载器、UI框架等。


## 如何编写Stable Scripts？

详细请参考[Stable Scripts](doc/StableScripts.md)文档。

目前支持的模型有：
- SD1
- SDXL
- Flux



## 设置开发环境

### 依赖项

首先，请检查您的设备上是否安装了以下依赖项。

- nodejs 和 yarn
  - 请从以下地址下载：https://nodejs.org/en/download
  - npm install --global yarn

- rustc 和 cargo
  - 请查看 https://www.rust-lang.org/tools/install


### Nodejs 和 Python 环境

以下命令将为您安装 yarn 包和 '.venv' 中的嵌入式 Python 环境以及必要的 Python 包。

```bash
yarn
```


### 运行开发服务器

要快速开始开发，您可以将桌面项目作为入口点运行：
```bash
yarn dev:desktop
```

或者为功能 UI 开发启动额外的热重载服务器：
```bash
yarn dev:desktop
yarn dev:functional_ui
```

或者您可以手动启动服务器、执行器、功能 UI 和桌面，这样可以给您更多的灵活性和清晰的消息：

```bash
yarn dev:server
yarn dev:executor
yarn dev:functional_ui
yarn dev:desktop
```

- 应用服务器：http://localhost:7422/
- API 文档服务器：http://localhost:7422/docs
- 功能 UI 开发服务器：http://localhost:7420/

### 不使用桌面项目运行示例

如果您正在开发功能 UI，您可以直接从网页浏览器运行它：

```bash
yarn dev:server
yarn dev:executor
yarn dev:functional_ui
```

示例 URL：
```
http://localhost:7420/?path=<example_path>/basic/workflow-sd1.py
```

### 下载测试模型

要测试图像生成，您需要以下模型，包括：

- SD1.5
- SDXL
- Flux

您可以从以下地址下载：
https://huggingface.co/datasets/sunxfancy/TestSDModels/tree/main 