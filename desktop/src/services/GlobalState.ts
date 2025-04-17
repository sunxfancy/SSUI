import { load } from '@tauri-apps/plugin-store';
import { invoke } from '@tauri-apps/api/core';

// 全局状态接口
export interface RootState {
  path: string;
  version: string;
}

// 全局状态管理器
class GlobalStateManager {
  private static instance: GlobalStateManager;
  private rootState: RootState | null = null;
  private isInitialized = false;

  private constructor() {}

  // 获取单例实例
  public static getInstance(): GlobalStateManager {
    if (!GlobalStateManager.instance) {
      GlobalStateManager.instance = new GlobalStateManager();
    }
    return GlobalStateManager.instance;
  }

  // 初始化全局状态
  public async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      const production = import.meta.env.PROD;
      
      if (!production) {
        const path: string = await invoke("get_dev_root");
        this.rootState = { path, version: 'dev' };
      } else {
        const store = await load('settings.json', { autoSave: true });
        const rootData = await store.get<RootState>('root');
        this.rootState = rootData || null;
      }
      
      this.isInitialized = true;
      console.log('全局状态初始化完成:', this.rootState);
    } catch (error) {
      console.error('初始化全局状态失败:', error);
    }
  }

  // 获取 root 路径
  public getRootPath(): string | null {
    return this.rootState?.path || null;
  }

  // 获取 root 版本
  public getRootVersion(): string | null {
    return this.rootState?.version || null;
  }

  // 获取完整的 root 状态
  public getRootState(): RootState | null {
    return this.rootState;
  }

  // 设置 root 状态
  public setRootState(state: RootState): void {
    this.rootState = state;
  }
}

export default GlobalStateManager; 