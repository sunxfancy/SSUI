构建系统
============================

我们的构建系统基于yarn和cargo，你需要先安装nodejs，rust，yarn和cargo。


## 基本构建

在项目根目录下，执行 `yarn` 会安装所有js依赖，下载一个python环境，在.venv目录创建开发虚拟环境，并安装所有python依赖。

开发时，执行 `yarn dev` 会启动所有开发服务器，并自动打开项目，并监听文件变化。
注意：现在yarn dev 稍微有点难用，server进行热更新时，会自动终结掉所有其他进程，导致刷新出问题

也可以手动启动独立的开发服务器：
```
yarn dev:desktop_ui
yarn dev:functional_ui
yarn dev:components
yarn dev:server
```
需要同时开启这4个进行项目集成开发，基本能满足所有项目代码热更新的需求。但如果你只需要单独测试某个部分，也可以只启动对应的服务器。


## 打包

执行 `yarn package` 会打包所有代码，并最终在desktop/src-tauri/target/release/bundle目录下生成最终的安装包。


## 构建目标

我们主要有6个构建目标：
- desktop 桌面端主项目  依赖 functional_ui, ssui_components, server
- functional_ui 基础UI界面  依赖 ssui_components
- ssui_components 基础组件
- server 服务器端 依赖 functional_ui
- ssui-vscode 插件 依赖 server, ssui_components
- extension_builder 扩展构建工具










