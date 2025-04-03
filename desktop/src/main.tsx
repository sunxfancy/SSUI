import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Install from "./Install";
import tray_init from "./tray.js";
import { load } from '@tauri-apps/plugin-store';
import { invoke } from '@tauri-apps/api/core';
import { BlueprintProvider } from "@blueprintjs/core";

// 载入样式
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "./App.css";

const production = import.meta.env.PROD;

function Root() {
  const [root, setRoot] = useState<{ path: string, version: string } | undefined>();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function initRoot() {
      try {
        if (!production) {
          const path: string = await invoke("get_dev_root");
          setRoot({ path, version: 'dev' });
        } else {
          const store = await load('settings.json', { autoSave: true });
          const rootData = await store.get<{ path: string, version: string }>('root');
          setRoot(rootData);
        }
        
        if (root?.path) {
          console.log('root path:', root.path);
          console.log('root version:', root.version);
          tray_init();
        }
      } catch (error) {
        console.error('初始化失败:', error);
      } finally {
        setIsLoading(false);
      }
    }

    initRoot();
  }, []);

  if (isLoading) {
    return <div>加载中...</div>;
  }

  return (
    <BlueprintProvider>
      {root?.path ? <App /> : <Install />}
    </BlueprintProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);