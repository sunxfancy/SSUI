import { IInstallerProvider } from '../providers/IInstallerProvider';

export class MockInstallerProvider implements IInstallerProvider {
  private mockPlatform = 'darwin';

  async getAppDataDir(): Promise<string> {
    return '/mock/app/data/dir';
  }

  async selectFolder(): Promise<string | null> {
    return '/mock/selected/folder';
  }

  async exitApp(): Promise<void> {
    console.log('模拟退出应用');
  }

  async relaunchApp(): Promise<void> {
    console.log('模拟重启应用');
  }

  async detectPlatform(): Promise<string> {
    return this.mockPlatform;
  }

  setMockPlatform(platform: string): void {
    this.mockPlatform = platform;
  }

  async createVirtualEnv(installDir: string) {
    const mockCommand = {
      onProgress: (callback: (data: string) => void) => {
        setTimeout(() => callback('创建虚拟环境中...'), 500);
        setTimeout(() => callback('虚拟环境创建完成'), 1000);
      },
      onError: (callback: (error: string) => void) => {},
      onComplete: (callback: (code: number) => void) => {
        setTimeout(() => callback(0), 1500);
      },
      execute: async () => {
        console.log('模拟执行创建虚拟环境命令');
      }
    };
    
    return mockCommand;
  }

  async installPackages(installDir: string, lockFile: string) {
    const mockCommand = {
      onProgress: (callback: (data: string) => void) => {
        setTimeout(() => callback('安装依赖包中...'), 500);
        setTimeout(() => callback('安装numpy...'), 1000);
        setTimeout(() => callback('安装pandas...'), 1500);
        setTimeout(() => callback('依赖包安装完成'), 2000);
      },
      onError: (callback: (error: string) => void) => {},
      onComplete: (callback: (code: number) => void) => {
        setTimeout(() => callback(0), 2500);
      },
      execute: async () => {
        console.log(`模拟执行安装依赖包命令，使用锁文件: ${lockFile}`);
      }
    };
    
    return mockCommand;
  }

  async saveSettings(installConfig: {
    path: string;
    version: string;
    platform: string;
    enableGPU?: boolean;
    enableAutoUpdate?: boolean;
  }): Promise<void> {
    console.log('模拟保存设置', installConfig);
  }
} 