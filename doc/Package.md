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

发布需要使用github的release功能，将打包好的文件上传到release中。



