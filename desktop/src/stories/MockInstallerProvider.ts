import { CommandInfo, IInstallerProvider } from '../providers/IInstallerProvider';

export class MockInstallerProvider implements IInstallerProvider {
  private mockPlatform = 'darwin';

  async getAppDataDir(): Promise<string> {
    return '/mock/app/data/dir';
  }

  async getUserDir(): Promise<string> {
    return '/mock/user/dir';
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

  async checkPythonInstalled(installDir: string): Promise<CommandInfo> {
    console.log(`检查Python安装: ${installDir}`);
    // 模拟Python已安装
    return {
      success: true,
      message: '已安装 Python 3.12.0'
    };
  }

  async downloadPython(installDir: string): Promise<CommandInfo> {
    console.log(`模拟下载Python: ${installDir}`);
    return {
      success: true,
      message: 'Python 3.12.0 下载并安装成功'
    };
  }

  async checkVirtualEnvExists(installDir: string): Promise<CommandInfo> {
    console.log(`检查虚拟环境: ${installDir}`);
    // 模拟虚拟环境不存在，需要创建
    return {
      success: false,
      message: '虚拟环境不存在'
    };
  }

  async createVirtualEnv(installDir: string): Promise<CommandInfo> {
    console.log(`模拟创建虚拟环境: ${installDir}`);
    await new Promise(resolve => setTimeout(resolve, 1000)); // 模拟延迟
    return {
      success: true,
      message: '虚拟环境创建成功'
    };
  }

  async checkPackagesInstalled(installDir: string): Promise<CommandInfo> {
    console.log(`检查包安装状态: ${installDir}`);
    // 模拟包未安装
    return {
      success: false,
      message: '依赖包未安装'
    };
  }

  async installPackages(installDir: string, lockFile: string): Promise<CommandInfo> {
    console.log(`模拟安装依赖包: ${installDir}, 使用锁文件: ${lockFile}`);
    await new Promise(resolve => setTimeout(resolve, 2000)); // 模拟延迟
    return {
      success: true,
      message: '依赖包安装成功'
    };
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