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
  shellOutput: string;
  currentPlatform: string;
}

interface InstallPageProps {
  provider?: IInstallerProvider;
}

class InstallPage extends React.Component<InstallPageProps, InstallPageState> {
  private provider: IInstallerProvider;
  
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
      shellOutput: '',
      currentPlatform: '',
    };
  }
  
  async componentDidMount() {
    const appDataDirPath = await this.provider.getAppDataDir();
    this.setState({ installDir: appDataDirPath });
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
    let progress = 0;
    let output = '开始安装...\n';
    this.setState({ shellOutput: output });

    // 模拟安装步骤和进度
    const interval = setInterval(async () => {
      progress += 10;
      output += `进度: ${progress}%\n`;

      this.setState({
        installProgress: progress,
        shellOutput: output,
      });

      if (progress >= 100) {
        clearInterval(interval);
      }
    }, 1000);
  }

  async detectPlatform() {
    const platformType = await this.provider.detectPlatform();
    this.setState({ currentPlatform: platformType });
    console.log('检测到平台:', platformType);
  }

  async installDependencies() {
    const { currentPlatform, installDir } = this.state;
    let lockFile = '';
    
    // 根据平台选择正确的lock文件
    if (currentPlatform === 'darwin') {
      lockFile = 'dependencies/macosx.lock';
      this.setState({ shellOutput: this.state.shellOutput + '检测到macOS系统，使用macosx.lock...\n' });
    } else if (currentPlatform === 'win32') {
      lockFile = 'dependencies/windows.lock';
      this.setState({ shellOutput: this.state.shellOutput + '检测到Windows系统，使用windows.lock...\n' });
    } else {
      // 假设Linux或其他系统使用macosx.lock
      lockFile = 'dependencies/macosx.lock';
      this.setState({ shellOutput: this.state.shellOutput + `检测到${currentPlatform}系统，使用macosx.lock作为默认选择...\n` });
    }

    try {
      // 创建一个虚拟环境
      this.setState({ 
        shellOutput: this.state.shellOutput + '正在创建Python虚拟环境...\n',
        installProgress: 10
      });
      
      const createVenvCommand = await this.provider.createVirtualEnv(installDir);
      
      createVenvCommand.onProgress((line) => {
        this.setState({ 
          shellOutput: this.state.shellOutput + line + '\n',
        });
      });
      
      createVenvCommand.onError((error) => {
        this.setState({ 
          shellOutput: this.state.shellOutput + `错误: ${error}\n`,
        });
      });
      
      createVenvCommand.onComplete(async (code) => {
        this.setState({ 
          shellOutput: this.state.shellOutput + `虚拟环境创建完成，退出代码: ${code}\n`,
          installProgress: 30
        });
        
        if (code === 0) {
          await this.installPackages(lockFile);
        } else {
          this.setState({ 
            shellOutput: this.state.shellOutput + '创建虚拟环境失败!\n',
          });
        }
      });
      
      await createVenvCommand.execute();
      
    } catch (error) {
      this.setState({ 
        shellOutput: this.state.shellOutput + `安装过程中出错: ${error}\n`,
      });
    }
  }
  
  async installPackages(lockFile: string) {
    const { installDir, currentPlatform, enableGPU, enableAutoUpdate } = this.state;
    
    this.setState({ 
      shellOutput: this.state.shellOutput + '正在安装依赖包...\n',
      installProgress: 40
    });
    
    try {
      const installCommand = await this.provider.installPackages(installDir, lockFile);
      
      installCommand.onProgress((line) => {
        // 更新进度
        const progress = Math.min(40 + Math.floor(Math.random() * 50), 99);
        this.setState({ 
          shellOutput: this.state.shellOutput + line + '\n',
          installProgress: progress
        });
      });
      
      installCommand.onError((error) => {
        this.setState({ 
          shellOutput: this.state.shellOutput + `警告: ${error}\n`,
        });
      });
      
      installCommand.onComplete(async (code) => {
        if (code === 0) {
          this.setState({ 
            shellOutput: this.state.shellOutput + '依赖包安装完成!\n',
            installProgress: 100,
            isInstalling: false
          });
          
          // 保存安装成功的配置
          await this.provider.saveSettings({ 
            path: installDir, 
            version: '0.1.0', 
            platform: currentPlatform,
            enableGPU,
            enableAutoUpdate
          });
          
          await this.provider.relaunchApp();
        } else {
          this.setState({ 
            shellOutput: this.state.shellOutput + `安装依赖失败，退出代码: ${code}\n`,
          });
        }
      });
      
      await installCommand.execute();
      
    } catch (error) {
      this.setState({ 
        shellOutput: this.state.shellOutput + `安装依赖时出错: ${error}\n`,
      });
    }
  }

  render() {
    const { isOpen, installDir, enableGPU, enableAutoUpdate, isInstalling, installProgress, shellOutput } = this.state;

    return (
      <div>
        <Dialog
          isOpen={isOpen}
          onClose={() => this.setState({ isOpen: false })}
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
              <ProgressBar value={installProgress / 100} />
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
