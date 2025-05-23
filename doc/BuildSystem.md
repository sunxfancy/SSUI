构建系统
============================

我们的构建系统基于yarn和cargo，你需要先安装nodejs，rust，yarn和cargo。


## 基本构建

在项目根目录下，执行 `yarn` 会安装所有js依赖，下载一个python环境，在.venv目录创建开发虚拟环境，并安装所有python依赖。

可以直接启动desktop项目进行开发：
```
yarn dev:desktop
```

也可以手动启动独立的开发服务器：
```
yarn dev:desktop
yarn dev:functional_ui
yarn dev:components
yarn dev:server
yarn dev:executor
```
需要同时开启这5个进行项目集成开发，基本能满足所有项目代码热更新的需求。但如果你只需要单独测试某个部分，也可以只启动对应的服务器。

注：dev:server和dev:executor并不是开发服务器，不会热更新，但可以方便观察其运行状态和输出，也可以选择查看项目目录下的log文件夹。另外如果手动启动dev:server则也必须手动启动dev:executor。


## 构建目标

我们主要有6个主要构建目标：
- `desktop` 桌面端主项目  依赖 `functional_ui`, `ssui_components`, `server`, `extension_builder`
- `functional_ui` 基础UI界面  依赖 `ssui_components`
- `ssui_components` 基础组件
- `server` 服务器端 依赖 `functional_ui`
- `ssui-vscode` 插件 依赖 `server`, `ssui_components`
- `extension_builder` 扩展构建工具

## 构建命令

项目提供了多个构建命令：

- `yarn dev:desktop_sb` - 启动桌面Storyboard开发服务器，用来独立开发React组件
- `yarn dev:desktop` - 启动Tauri桌面应用开发服务器，**最常用**，如果当前系统没有占用7422端口，则会自动启动server和executor
- `yarn dev:server` - 启动FastAPI服务器（端口7422）
- `yarn dev:executor` - 启动SSExecutor用来执行任务，运行模型
- `yarn dev:functional_ui` - 启动功能UI开发服务器(端口7420)，desktop项目启动时，如果发现7420端口被占用，则会自动用开发用端口7420代替7422
- `yarn dev:components` - 启动组件开发服务器，自动watch组件代码变化

构建命令：
- `yarn build:desktop` - 构建Tauri桌面应用
- `yarn build:components` - 构建组件
- `yarn build:functional_ui` - 构建功能UI
- `yarn build:example` - 构建示例扩展

## 打包

执行 `yarn package` 会打包所有代码，并最终在`desktop/src-tauri/target/release/bundle`目录下生成最终的安装包。

## 扩展打包

项目支持多个扩展的打包：
- `yarn ext:package` - 打包所有扩展
- `yarn ext:package_Image` - 打包Image扩展
- `yarn ext:package_Video` - 打包Video扩展
- `yarn ext:package_Audio` - 打包Audio扩展

## 测试

- `yarn test` - 运行所有测试
- `yarn test_on <test_name>` - 运行指定测试，例如`yarn test_on ss_executor_test`

请注意，测试分为normal和slow两种，slow测试会消耗更多时间，并依赖一些大型的模型，默认不会运行。如需要，设置环境变量`RUN_SLOW_TESTS=1`来运行slow测试。

## 依赖管理

- `yarn check_deps` - 检查依赖版本
- `yarn requirements` - 生成Python依赖文件
- `yarn install-requirements` - 安装Python依赖
- `yarn update-lock` - 更新依赖锁定文件
- `yarn update-lock:no-upgrade` - 更新依赖锁定文件（但不升级版本，这在添加新依赖时非常有用）

如果不想记太多命令，直接执行`yarn`，它会自动更新安装所有依赖








