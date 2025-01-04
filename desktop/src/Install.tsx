import React from 'react';
import { Dialog, Button, Checkbox, FormGroup, InputGroup, Intent, Classes, ProgressBar, Callout } from '@blueprintjs/core';
import { exit, relaunch } from '@tauri-apps/plugin-process';
import { load } from '@tauri-apps/plugin-store';
import { appDataDir } from '@tauri-apps/api/path';
import { open } from '@tauri-apps/plugin-dialog';  // Tauri Dialog API用于选择目录


const appDataDirPath = await appDataDir();

interface InstallPageState {
  isOpen: boolean;
  installDir: string;
  enableGPU: boolean;
  enableAutoUpdate: boolean;
  isInstalling: boolean;
  installProgress: number;
  shellOutput: string;
}

class InstallPage extends React.Component<{}, InstallPageState> {
  constructor(props: {}) {
    super(props);
    this.state = {
      isOpen: true,
      installDir: appDataDirPath,
      enableGPU: true,
      enableAutoUpdate: true,
      isInstalling: false,
      installProgress: 0,
      shellOutput: '',
    };
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

    console.log('Install Directory:', installDir);
    console.log('Enable GPU:', enableGPU);
    console.log('Enable Auto Update:', enableAutoUpdate);

    // Start the installation process
    this.setState({ isOpen: false, isInstalling: true, installProgress: 0, shellOutput: '' });
    this.simulateInstallation();
  }

  async handleCancel() {
    // Close the current window when cancel is clicked using Tauri's window.close()
    await exit();
  }

  // Handle folder selection via Tauri Dialog API
  async handleSelectFolder() {
    const selectedFolder = await open({
      directory: true, // Open folder selection dialog
      multiple: false, // Allow only one folder selection
    });
    if (selectedFolder) {
      this.setState({ installDir: selectedFolder as string });
    }
  };

  simulateInstallation() {
    let progress = 0;
    let output = 'Starting installation...\n';
    this.setState({ shellOutput: output });

    // Simulate installation steps and progress
    const interval = setInterval(async () => {
      progress += 10;
      output += `Progress: ${progress}%\n`;

      this.setState({
        installProgress: progress,
        shellOutput: output,
      });

      if (progress >= 100) {
        clearInterval(interval);
        this.setState({ shellOutput: output + 'Installation complete!\n', isInstalling: false });
        // 写入安装成功的配置
        const store = await load('settings.json', { autoSave: false });
        await store.set('root', { path: this.state.installDir, version: '0.1.0' });
        await store.save();
        await relaunch();
      }
    }, 1000);
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
