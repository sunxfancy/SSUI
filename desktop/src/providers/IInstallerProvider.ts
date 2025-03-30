export interface IInstallerProvider {
  // 基本配置相关
  getAppDataDir(): Promise<string>;
  selectFolder(): Promise<string | null>;
  exitApp(): Promise<void>;
  relaunchApp(): Promise<void>;
  
  // 平台检测
  detectPlatform(): Promise<string>;
  
  // 安装过程
  createVirtualEnv(installDir: string): Promise<{
    onProgress: (callback: (data: string) => void) => void;
    onError: (callback: (error: string) => void) => void;
    onComplete: (callback: (code: number) => void) => void;
    execute: () => Promise<void>;
  }>;
  
  installPackages(installDir: string, lockFile: string): Promise<{
    onProgress: (callback: (data: string) => void) => void;
    onError: (callback: (error: string) => void) => void;
    onComplete: (callback: (code: number) => void) => void;
    execute: () => Promise<void>;
  }>;
  
  // 配置存储
  saveSettings(installConfig: {
    path: string;
    version: string;
    platform: string;
    enableGPU?: boolean;
    enableAutoUpdate?: boolean;
  }): Promise<void>;
} 