import React from 'react';
import { Dialog, Button, Checkbox, FormGroup, InputGroup, Intent, Classes, ProgressBar, Callout } from '@blueprintjs/core';
import { IInstallerProvider } from './providers/IInstallerProvider';
import { TauriInstallerProvider } from './providers/TauriInstallerProvider';

interface InstallPageState {
  isOpen: boolean;
  installDir: string;
  enableGPU: boolean;
  enableAutoUpdate: boolean;
  isInstalling: boolean;
  installProgress: number;
  predictProgress: number;
  currentProgress: number;
  shellOutput: string;
  currentPlatform: string;
}

interface InstallPageProps {
  provider?: IInstallerProvider;
}

class InstallPage extends React.Component<InstallPageProps, InstallPageState> {
  private provider: IInstallerProvider;
  private _progressInterval: number | undefined;

  constructor(props: InstallPageProps) {
    super(props);
    this.provider = props.provider || new TauriInstallerProvider();

    this.state = {
      isOpen: true,
      installDir: '',
      enableGPU: true,
      enableAutoUpdate: true,
      isInstalling: false,
      installProgress: 0,
      predictProgress: 0,
      currentProgress: 0,
      shellOutput: '',
      currentPlatform: '',
    };
  }

  async componentDidMount() {
    const userDirPath = await this.provider.getUserDir();
    this.setState({ installDir: userDirPath });
    await this.detectPlatform();
  }

  handleInstallDirChange(event: React.ChangeEvent<HTMLInputElement>) {
    this.setState({ installDir: event.target.value });
  }

  handleGPUChange(event: React.ChangeEvent<HTMLInputElement>) {
    this.setState({ enableGPU: event.target.checked });
  }

  handleAutoUpdateChange(event: React.ChangeEvent<HTMLInputElement>) {
    this.setState({ enableAutoUpdate: event.target.checked });
  }

  handleSubmit() {
    const { installDir, enableGPU, enableAutoUpdate } = this.state;

    console.log('安装目录:', installDir);
    console.log('启用GPU:', enableGPU);
    console.log('启用自动更新:', enableAutoUpdate);

    // 开始安装过程
    this.setState({ isOpen: false, isInstalling: true, installProgress: 0, shellOutput: '' });
    this.simulateInstallation();
    this.installDependencies();
  }

  async handleCancel() {
    await this.provider.exitApp();
  }

  // 通过Provider处理文件夹选择
  async handleSelectFolder() {
    const selectedFolder = await this.provider.selectFolder();
    if (selectedFolder) {
      this.setState({ installDir: selectedFolder });
    }
  };

  simulateInstallation() {
    // 清除可能存在的旧定时器
    if (this._progressInterval) {
      clearInterval(this._progressInterval);
    }
    
    // 初始化进度值
    this.setState({ 
      currentProgress: 0,
      installProgress: 0,
      predictProgress: 10 // 初始预估进度设为10%
    });

    // 创建内部变量跟踪实际进度值
    let internalProgress = 0;

    // 创建定时器，每100ms更新一次进度
    this._progressInterval = setInterval(() => {
      const { installProgress, predictProgress } = this.state;
      
      if (internalProgress >= installProgress) {
        // 向预估进度移动，速度为2%/s，即每100ms增加0.2%
        if (internalProgress < predictProgress) {
          // 如果距离installProgress只有5%以内，则速度会越来越慢
          if (internalProgress > installProgress && internalProgress - installProgress <= 5) {
            // 计算减速因子：差距越小，速度越慢
            const slowdownFactor = (internalProgress - installProgress) / 5;
            internalProgress += 0.2 * slowdownFactor;
          } else {
            internalProgress += 0.2; // 正常速度2%/s
          }
        }
      } else {
        // 追赶真实进度，速度为4%/s，即每100ms增加0.4%
        internalProgress += 0.4;
      }
      
      // 只有当进度值达到新的整数时才更新状态
      const currentFloor = Math.floor(this.state.currentProgress);
      const newFloor = Math.floor(internalProgress);
      
      if (newFloor > currentFloor) {
        this.setState({ currentProgress: newFloor });
      }
      
      // 如果安装完成，清除定时器
      if (installProgress >= 100 && internalProgress >= 100) {
        clearInterval(this._progressInterval);
        this._progressInterval = undefined;
        // 确保最终显示100%
        this.setState({ currentProgress: 100 });
      }
    }, 100);
  }

  async detectPlatform() {
    const platformType = await this.provider.detectPlatform();
    this.setState({ currentPlatform: platformType });
    console.log('检测到平台:', platformType);
  }

  async installDependencies() {
    const { currentPlatform, installDir, enableGPU, enableAutoUpdate } = this.state;
    let lockFile = '';

    // 根据平台选择正确的lock文件
    if (currentPlatform === 'macos') {
      lockFile = 'dependencies/macosx.lock';
      this.setState({ shellOutput: this.state.shellOutput + '检测到macOS系统，使用macosx.lock...\n' });
    } else if (currentPlatform === 'windows') {
      lockFile = 'dependencies/windows.lock';
      this.setState({ shellOutput: this.state.shellOutput + '检测到Windows系统，使用windows.lock...\n' });
    } else {
      // 假设Linux或其他系统使用macosx.lock
      lockFile = 'dependencies/macosx.lock';
      this.setState({ shellOutput: this.state.shellOutput + `检测到${currentPlatform}系统，使用macosx.lock作为默认选择...\n` });
    }

    try {
      // 1. 检查Python是否已安装
      this.setState(prev => ({
        shellOutput: prev.shellOutput + '正在检查Python是否已安装...\n',
        installProgress: 1,
        predictProgress: 2
      }));
      
      let pythonResult = await this.provider.checkPythonInstalled(installDir);
      this.setState(prev => ({
        shellOutput: prev.shellOutput + pythonResult.message + '\n',
        installProgress: 2
      }));

      // 2. 如果Python未安装，下载并安装
      if (!pythonResult.success) {
        this.setState(prev => ({
          shellOutput: prev.shellOutput + '正在下载Python3.12到目录' + installDir + '...\n',
          predictProgress: 10
        }));
        
        const downloadResult = await this.provider.downloadPython(installDir);
        this.setState(prev => ({
          shellOutput: prev.shellOutput + downloadResult.message + '\n',
          installProgress: 10
        }));
        
        if (!downloadResult.success) {
          this.setState(prev => ({
            shellOutput: prev.shellOutput + '下载Python失败，安装中止。\n',
            installProgress: 10
          }));
          return;
        }
      }

      // 3. 检查虚拟环境是否存在
      this.setState(prev => ({
        shellOutput: prev.shellOutput + '正在检查虚拟环境...\n',
        installProgress: 11,
        predictProgress: 15
      }));
      
      const venvResult = await this.provider.checkVirtualEnvExists(installDir);
      this.setState(prev => ({
        shellOutput: prev.shellOutput + venvResult.message + '\n',
        installProgress: 12
      }));

      // 4. 如果虚拟环境不存在，创建虚拟环境
      if (!venvResult.success) {
        this.setState(prev => ({
          shellOutput: prev.shellOutput + '正在创建Python虚拟环境...\n',
          installProgress: 13,
        }));
        
        const createVenvResult = await this.provider.createVirtualEnv(installDir);
        this.setState(prev => ({
          shellOutput: prev.shellOutput + createVenvResult.message + '\n',
          installProgress: 15,
        }));
        
        if (!createVenvResult.success) {
          this.setState(prev => ({
            shellOutput: prev.shellOutput + '创建虚拟环境失败，安装中止。\n',
            installProgress: 15
          }));
          return;
        }
      }

      // 5. 检查包是否已安装
      this.setState(prev => ({
        shellOutput: prev.shellOutput + '正在检查依赖包...\n',
        installProgress: 16,
        predictProgress: 20
      }));
      
      const packagesResult = await this.provider.checkPackagesInstalled(installDir);
      this.setState(prev => ({
        shellOutput: prev.shellOutput + packagesResult.message + '\n',
        installProgress: 20
      }));

      // 6. 如果包未安装，安装包
      if (!packagesResult.success) {
        this.setState(prev => ({
          shellOutput: prev.shellOutput + '正在安装依赖包...\n',
          predictProgress: 95
        }));
        
        const installResult = await this.provider.installPackages(installDir, lockFile);
        this.setState(prev => ({
          shellOutput: prev.shellOutput + installResult.message + '\n',
          installProgress: 95
        }));
        
        if (!installResult.success) {
          this.setState(prev => ({
            shellOutput: prev.shellOutput + '安装依赖包失败，安装中止。\n',
          }));
          return;
        }
      }

      // 7. 保存配置并完成
      this.setState(prev => ({
        shellOutput: prev.shellOutput + '正在保存配置...\n',
        installProgress: 95,
        predictProgress: 100
      }));
      
      await this.provider.saveSettings({
        path: installDir,
        version: '0.1.0',
        platform: currentPlatform,
        enableGPU,
        enableAutoUpdate
      });
      
      this.setState(prev => ({
        shellOutput: prev.shellOutput + '安装成功完成！即将重启应用...\n',
        installProgress: 100,
        predictProgress: 100,
        isInstalling: false
      }));
      
      // 延迟一小段时间后重启应用
      setTimeout(async () => {
        await this.provider.relaunchApp();
      }, 1000);

    } catch (error) {
      this.setState(prev => ({
        shellOutput: prev.shellOutput + `安装过程中出错: ${error}\n`,
      }));
    }
  }

  // 组件卸载时清理定时器
  componentWillUnmount() {
    if (this._progressInterval) {
      clearInterval(this._progressInterval);
    }
  }

  render() {
    const { isOpen, installDir, enableGPU, enableAutoUpdate, isInstalling, currentProgress, shellOutput } = this.state;

    return (
      <div>
        <Dialog
          isOpen={isOpen}
          isCloseButtonShown={false}
          title="Installation"
        >
          <div className={Classes.DIALOG_BODY}>
            <FormGroup label="Installation Directory" labelFor="install-dir" fill={true}>
              <InputGroup fill={true}
                id="install-dir"
                type="text"
                placeholder="Enter installation directory"
                value={installDir}
                onChange={this.handleInstallDirChange.bind(this)}
                rightElement={<Button
                  icon="folder-open"
                  minimal
                  onClick={this.handleSelectFolder.bind(this)}
                />}
              />
            </FormGroup >

            <FormGroup>
              <Checkbox
                label="Enable GPU"
                checked={enableGPU}
                onChange={this.handleGPUChange.bind(this)}
              />
              <Checkbox
                label="Enable Auto Update"
                checked={enableAutoUpdate}
                onChange={this.handleAutoUpdateChange.bind(this)}
              />
            </FormGroup>
          </div>

          <div className={Classes.DIALOG_FOOTER}>
            <Button text="Cancel" onClick={this.handleCancel.bind(this)} />
            <Button text="Install" onClick={this.handleSubmit.bind(this)} intent={Intent.PRIMARY} />
          </div>
        </Dialog >

        {/* Progress and shell output after dialog is closed */}
        {
          isInstalling && (
            <div style={{ marginTop: '20px' }}>
              <ProgressBar value={currentProgress / 100} />
              <Callout intent={Intent.PRIMARY} style={{ marginTop: '10px' }}>
                <pre>{shellOutput}</pre>
              </Callout>
            </div>
          )
        }
      </div >
    );
  }
}

export default InstallPage;
