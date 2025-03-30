// 命令执行结果信息
export interface CommandInfo {
  success: boolean;
  message: string;
}

export interface IInstallerProvider {
  // 基本配置相关
  getAppDataDir(): Promise<string>;
  getUserDir(): Promise<string>;
  selectFolder(): Promise<string | null>;
  exitApp(): Promise<void>;
  relaunchApp(): Promise<void>;
  
  // 平台检测
  detectPlatform(): Promise<string>;
  
  // 检测Python是否已安装
  checkPythonInstalled(installDir: string): Promise<CommandInfo>;
  
  // 下载Python3.12
  downloadPython(installDir: string): Promise<CommandInfo>;

  // 检测虚拟环境是否已创建
  checkVirtualEnvExists(installDir: string): Promise<CommandInfo>;
  
  // 创建虚拟环境
  createVirtualEnv(installDir: string): Promise<CommandInfo>;
  
  // 检测包是否已安装
  checkPackagesInstalled(installDir: string): Promise<CommandInfo>;
  
  // 安装包
  installPackages(installDir: string, lockFile: string): Promise<CommandInfo>;
  
  // 配置存储
  saveSettings(installConfig: {
    path: string;
    version: string;
    platform: string;
    enableGPU?: boolean;
    enableAutoUpdate?: boolean;
  }): Promise<void>;
} 