# Desktop 应用

这个目录存放的是整个SSUI应用的代码，使用Tauri制作，负责提供左边栏、tab页面管理、服务器管理以及安装等功能的实现。

## 开发方式

在本层级目录下，运行：

```
yarn tauri dev
```

或者在项目根目录运行：
```
yarn dev:desktop
```

如果只想开发UI，可以只启动Vite服务器:
```
yarn dev
```

根目录的 `yarn build:desktop_ui` 只构建桌面 UI。若要启动独立的 UI 开发服务器，请在本目录运行 `yarn dev`。

独立开发某个 React 控件，可以启动 Storybook：
```
yarn storybook
```

如果需要测试安装流程，可以设置NODE_ENV：
```
NODE_ENV=production yarn tauri dev
```

