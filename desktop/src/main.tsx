import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Install from "./Install";
import tray_init from "./tray.js";
import { load } from '@tauri-apps/plugin-store';
import { BlueprintProvider } from "@blueprintjs/core";

// 载入样式
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "./App.css";

const store = await load('settings.json', { autoSave: true });
const root = await store.get<{ path: string, version: string }>('root');

if (root && root.path) {
  // 运行主程序
  console.log('root path:', root.path);
  console.log('root version:', root.version);

  tray_init();

  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <BlueprintProvider>
        <App />
      </BlueprintProvider>
    </React.StrictMode>,
  );

} else {
  // 运行安装程序

  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <BlueprintProvider>
        <Install />
      </BlueprintProvider>
    </React.StrictMode>,
  );

}