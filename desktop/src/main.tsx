import React, { Component } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Install from "./Install";
import tray_init from "./tray.js";
import { load } from '@tauri-apps/plugin-store';
import { invoke } from '@tauri-apps/api/core';
import { BlueprintProvider } from "@blueprintjs/core";
import GlobalStateManager from "./services/GlobalState";
import ExecutorService from "./services/Executor";
import ServerService from "./services/Server";

// 载入样式
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "./App.css";

const production = import.meta.env.PROD;

interface RootState {
  root?: { path: string, version: string };
  isLoading: boolean;
}

class Root extends Component<{}, RootState> {
  private isInitialized: boolean = false;

  constructor(props: {}) {
    super(props);
    this.state = {
      root: undefined,
      isLoading: true
    };
  }

  async initRoot() {
    // 如果已经初始化过，则直接返回
    if (this.isInitialized) return;
    
    try {
      // 标记为已初始化
      this.isInitialized = true;
      
      // 初始化全局状态
      await GlobalStateManager.getInstance().initialize();
      
      // 从全局状态获取 root 信息
      const rootState = GlobalStateManager.getInstance().getRootState();
      this.setState({ root: rootState || undefined });
      
      if (rootState?.path) {
        console.log('root path:', rootState.path);
        console.log('root version:', rootState.version);
        tray_init();
        
        // 自动启动服务
        try {
          // 启动执行器服务
          const executorResult = await ExecutorService.getInstance().startExecutor();
          console.log('执行器服务启动结果:', executorResult.message);
          
          // 启动服务器服务
          const serverResult = await ServerService.getInstance().startServer();
          console.log('服务器服务启动结果:', serverResult.message);
        } catch (error) {
          console.error('启动服务时出错:', error);
        }
      }
    } catch (error) {
      console.error('初始化失败:', error);
    } finally {
      this.setState({ isLoading: false });
    }
  }

  componentDidMount() {
    this.initRoot();
  }

  render() {
    const { root, isLoading } = this.state;

    if (isLoading) {
      return <div>加载中...</div>;
    }

    return (
      <BlueprintProvider>
        {root?.path ? <App /> : <Install />}
      </BlueprintProvider>
    );
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);