import { exit, relaunch } from '@tauri-apps/plugin-process';
import { load } from '@tauri-apps/plugin-store';
import { appDataDir, homeDir, join, resolveResource } from '@tauri-apps/api/path';
import { open } from '@tauri-apps/plugin-dialog';
import { Command } from '@tauri-apps/plugin-shell';
import { platform } from '@tauri-apps/plugin-os';
import { IInstallerProvider, CommandInfo } from './IInstallerProvider';
import { exists, writeTextFile } from '@tauri-apps/plugin-fs';
import { invoke } from '@tauri-apps/api/core';

export class TauriInstallerProvider implements IInstallerProvider {
    async getAppDataDir(): Promise<string> {
        return await appDataDir();
    }

    async getUserDir(): Promise<string> {
        return await join(await homeDir(), 'SSUI');
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

    async checkPythonInstalled(installDir: string): Promise<CommandInfo> {
        const currentPlatform = await this.detectPlatform();
        const pythonPath = await join(installDir, currentPlatform === 'windows' ? 'python\\python.exe' : 'bin/python3');

        try {
            // 检查Python可执行文件是否存在
            console.log(pythonPath);
            const fileExists = await exists(pythonPath);
            if (!fileExists) {
                return {
                    success: false,
                    message: '目标版本Python未安装'
                };
            }

            // 验证Python版本
            console.log(installDir);

            const output = await invoke('run_python',
                {
                    path: pythonPath,
                    cwd: installDir,
                    args: ['--version']
                });

            return {
                success: true,
                message: `Python已安装: ${output}`
            };

        } catch (error) {
            return {
                success: false,
                message: `检查Python安装时出错: ${error}`
            };
        }
    }

    async downloadPython(installDir: string): Promise<CommandInfo> {
        const currentPlatform = await this.detectPlatform();
        let architecture = '';
        if (currentPlatform === 'windows') {
            architecture = 'x86_64-pc-windows-msvc';
        } else if (currentPlatform === 'macos') {
            architecture = 'aarch64-apple-darwin';
        } else if (currentPlatform === 'linux') {
            architecture = 'x86_64-unknown-linux-gnu';
        }

        try {
            const output: any = await invoke('download_python', {
                version: '3.12.8',
                release_date: '20241219',
                architecture: architecture,
                path: installDir
            });
            console.log(output);

            if (output == 'success') {
                return {
                    success: true,
                    message: 'Python 3.12 下载并安装成功'
                };
            } else {
                return {
                    success: false,
                    message: `Python下载失败: ${output.stderr}`
                };
            }
        } catch (error) {
            return {
                success: false,
                message: `Python下载过程出错: ${error}`
            };
        }
    }

    async checkVirtualEnvExists(installDir: string): Promise<CommandInfo> {
        const currentPlatform = await this.detectPlatform();
        const venvPath = `${installDir}/venv`;
        const activatePath = currentPlatform === 'windows'
            ? `${venvPath}/Scripts/activate.bat`
            : `${venvPath}/bin/activate`;

        try {
            const fileExists = await exists(activatePath);
            if (fileExists) {
                return {
                    success: true,
                    message: '虚拟环境已存在'
                };
            } else {
                return {
                    success: false,
                    message: '虚拟环境不存在'
                };
            }
        } catch (error) {
            return {
                success: false,
                message: `检查虚拟环境时出错: ${error}`
            };
        }
    }

    async createVirtualEnv(installDir: string): Promise<CommandInfo> {
        const currentPlatform = await this.detectPlatform();
        const pythonPath = await join(installDir, currentPlatform === 'windows' ? 'python\\python.exe' : 'bin/python3');

        try {
            const output = await invoke('run_python',
                {
                    path: pythonPath,
                    cwd: installDir,
                    args: ['-m', 'venv', await join(installDir, 'venv')]
                });

            return {
                success: true,
                message: '虚拟环境创建成功: ' + output
            };
        } catch (error) {
            return {
                success: false,
                message: `创建虚拟环境过程出错: ${error}`
            };
        }
    }

    async checkPackagesInstalled(installDir: string): Promise<CommandInfo> {
        // 检查安装完成标记文件
        const completionMarker = await join(installDir,'venv', '.packages_installed');

        try {
            const markerExists = await exists(completionMarker);
            if (markerExists) {
                return {
                    success: true,
                    message: '依赖包已安装'
                };
            }
            return {
                success: false,
                message: '依赖包未安装'
            };
        } catch (error) {
            return {
                success: false,
                message: `检查包安装状态时出错: ${error}`
            };
        }
    }

    async installPackages(installDir: string, lockFile: string): Promise<CommandInfo> {
        const currentPlatform = await this.detectPlatform();
        const pipPath = currentPlatform === 'windows'
            ? `${installDir}/venv/Scripts/pip.exe`
            : `${installDir}/venv/bin/pip`;

        const completionMarker = await join(installDir,'venv', '.packages_installed');

        try {

            // 如果标记不存在，检查pip是否可用
            const pipExists = await exists(pipPath);
            if (!pipExists) {
                return {
                    success: false,
                    message: 'pip不可用，请先创建虚拟环境'
                };
            }

            const resourcePath = await resolveResource(await join('resources', lockFile));

            const output = await invoke('run_python', 
                {
                    path: pipPath,
                    cwd: installDir,
                    args:  ['install', '-r', resourcePath]
                }
            );
            console.log('安装依赖包: ' + output);

            await writeTextFile(completionMarker, '');

            return {
                success: true,
                message: '依赖包安装成功: '
            };
        } catch (error) {
            return {
                success: false,
                message: `安装依赖包时出错: ${error}`
            };
        }
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