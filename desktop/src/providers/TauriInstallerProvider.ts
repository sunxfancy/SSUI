import { exit, relaunch } from '@tauri-apps/plugin-process';
import { load } from '@tauri-apps/plugin-store';
import { appDataDir, resolveResource } from '@tauri-apps/api/path';
import { open } from '@tauri-apps/plugin-dialog';
import { Command } from '@tauri-apps/plugin-shell';
import { platform } from '@tauri-apps/plugin-os';
import { IInstallerProvider } from './IInstallerProvider';

export class TauriInstallerProvider implements IInstallerProvider {
  async getAppDataDir(): Promise<string> {
    return await appDataDir();
  }

  async selectFolder(): Promise<string | null> {
    const result = await open({
      directory: true,
      multiple: false,
    });
    return result ? result as string : null;
  }

  async exitApp(): Promise<void> {
    await exit();
  }

  async relaunchApp(): Promise<void> {
    await relaunch();
  }

  async detectPlatform(): Promise<string> {
    return await platform();
  }

  async createVirtualEnv(installDir: string) {
    const currentPlatform = await this.detectPlatform();
    const pythonCmd = currentPlatform === 'win32' ? 'python' : 'python3';
    const createVenvCmd = Command.create(pythonCmd, ['-m', 'venv', `${installDir}/venv`]);
    
    return {
      onProgress: (callback: (data: string) => void) => {
        createVenvCmd.stdout.on('data', callback);
      },
      onError: (callback: (error: string) => void) => {
        createVenvCmd.stderr.on('data', callback);
        createVenvCmd.on('error', callback);
      },
      onComplete: (callback: (code: number) => void) => {
        createVenvCmd.on('close', data => callback(data?.code ?? 0));
      },
      execute: async () => {
        await createVenvCmd.execute();
      }
    };
  }

  async installPackages(installDir: string, lockFile: string) {
    const currentPlatform = await this.detectPlatform();
    const pipPath = currentPlatform === 'win32' 
      ? `${installDir}/venv/Scripts/pip` 
      : `${installDir}/venv/bin/pip`;
    
    const installCmd = Command.create(pipPath, ['install', '-r', lockFile]);
    
    return {
      onProgress: (callback: (data: string) => void) => {
        installCmd.stdout.on('data', callback);
      },
      onError: (callback: (error: string) => void) => {
        installCmd.stderr.on('data', callback);
        installCmd.on('error', callback);
      },
      onComplete: (callback: (code: number) => void) => {
        installCmd.on('close', data => callback(data?.code ?? 0));
      },
      execute: async () => {
        await installCmd.execute();
      }
    };
  }

  async saveSettings(installConfig: {
    path: string;
    version: string;
    platform: string;
    enableGPU?: boolean;
    enableAutoUpdate?: boolean;
  }): Promise<void> {
    const store = await load('settings.json', { autoSave: false });
    await store.set('root', installConfig);
    await store.save();
  }
} 