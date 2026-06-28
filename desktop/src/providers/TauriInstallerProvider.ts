import { exit, relaunch } from '@tauri-apps/plugin-process';
import { load } from '@tauri-apps/plugin-store';
import { appDataDir, homeDir, join, resolveResource } from '@tauri-apps/api/path';
import { open } from '@tauri-apps/plugin-dialog';
import { platform } from '@tauri-apps/plugin-os';
import { IInstallerProvider, CommandInfo } from './IInstallerProvider';
import { exists, readDir, writeTextFile, remove } from '@tauri-apps/plugin-fs';
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

    async selectFile(extensions?: string[]): Promise<string | null> {
        const result = await open({
            directory: false,
            multiple: false,
            filters: extensions && extensions.length > 0
                ? [{ name: '离线安装包', extensions }]
                : undefined,
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
        const pythonPath = await join(installDir, currentPlatform === 'windows' ? '.venv\\python\\python.exe' : '.venv/bin/python3');

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
                path: await join(installDir, '.venv')
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
        const venvPath = `${installDir}/.venv`;
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
        const pythonPath = await join(installDir, currentPlatform === 'windows' ? '.venv\\python\\python.exe' : '.venv/bin/python3');

        try {
            const output = await invoke('run_python',
                {
                    path: pythonPath,
                    cwd: installDir,
                    args: ['-m', 'venv', await join(installDir, '.venv')]
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
            ? `${installDir}\\.venv\\Scripts\\pip.exe`
            : `${installDir}/.venv/bin/pip`;

        const completionMarker = await join(installDir,'.venv', '.packages_installed');

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

    // 离线包解压目录（位于安装目录下，避免跨盘/权限问题）
    private async offlineExtractDir(installDir: string): Promise<string> {
        return await join(installDir, '.offline_pkg');
    }

    // 确保离线包已解压到固定目录（只解压一次，Python 与依赖安装步骤共用）
    private async ensureOfflineExtracted(installDir: string, offlineInstallerPath: string): Promise<string> {
        const extractDir = await this.offlineExtractDir(installDir);
        // 以 manifest.json 是否存在作为“已解压”的标志
        const marker = await join(extractDir, 'manifest.json');
        if (await exists(marker)) {
            return extractDir;
        }
        if (!(await exists(offlineInstallerPath))) {
            throw new Error(`离线安装包不存在: ${offlineInstallerPath}`);
        }
        if (await exists(extractDir)) {
            await remove(extractDir, { recursive: true });
        }
        // .pkg 实为 tar.gz，复用后端 unpack_app 解压
        await invoke('unpack_app', {
            tar_path: offlineInstallerPath,
            target_path: extractDir
        });
        return extractDir;
    }

    async installPythonOffline(installDir: string, offlineInstallerPath: string): Promise<CommandInfo> {
        try {
            const extractDir = await this.ensureOfflineExtracted(installDir, offlineInstallerPath);

            // 离线包中的 python/ 目录内含 python-build-standalone 的 tar.gz
            const pythonDir = await join(extractDir, 'python');
            if (!(await exists(pythonDir))) {
                return {
                    success: false,
                    message: '离线安装包未包含 Python'
                };
            }
            const entries = await readDir(pythonDir);
            const archive = entries.find(e => e.isFile && (e.name.endsWith('.tar.gz') || e.name.endsWith('.tgz')));
            if (!archive) {
                return {
                    success: false,
                    message: '离线安装包的 python/ 中未找到 Python 压缩包'
                };
            }

            // 解压到 .venv，使其形成 .venv/python/...（与在线 downloadPython 一致）
            const archivePath = await join(pythonDir, archive.name);
            const venvPath = await join(installDir, '.venv');
            await invoke('unpack_app', {
                tar_path: archivePath,
                target_path: venvPath
            });

            return {
                success: true,
                message: '离线 Python 安装成功'
            };
        } catch (error) {
            return {
                success: false,
                message: `离线安装 Python 时出错: ${error}`
            };
        }
    }

    async installPackagesOffline(installDir: string, offlineInstallerPath: string): Promise<CommandInfo> {
        const currentPlatform = await this.detectPlatform();
        const pipPath = currentPlatform === 'windows'
            ? `${installDir}\\.venv\\Scripts\\pip.exe`
            : `${installDir}/.venv/bin/pip`;

        const completionMarker = await join(installDir, '.venv', '.packages_installed');

        try {
            const pipExists = await exists(pipPath);
            if (!pipExists) {
                return {
                    success: false,
                    message: 'pip不可用，请先创建虚拟环境'
                };
            }

            // 1. 确保离线包已解压（若 Python 步骤已解压则直接复用）
            const extractDir = await this.ensureOfflineExtracted(installDir, offlineInstallerPath);

            // 2. 在解压目录中定位 lock 文件与 packages 目录
            const entries = await readDir(extractDir);
            const lockEntry = entries.find(e => e.isFile && e.name.endsWith('.lock'));
            if (!lockEntry) {
                return {
                    success: false,
                    message: '离线安装包中未找到 .lock 文件'
                };
            }
            const lockPath = await join(extractDir, lockEntry.name);
            const packagesDir = await join(extractDir, 'packages');
            const constraintsPath = await join(extractDir, 'constraints.txt');

            // 3. 离线安装：--no-index 完全不联网，--find-links 指向本地包目录，
            //    -c constraints.txt 钉 setuptools<81 以兼容老 sdist 的构建
            const args = ['install', '--no-index', '--find-links', packagesDir, '-r', lockPath];
            if (await exists(constraintsPath)) {
                args.push('-c', constraintsPath);
            }

            const output = await invoke('run_python',
                {
                    path: pipPath,
                    cwd: installDir,
                    args: args
                }
            );
            console.log('离线安装依赖包: ' + output);

            await writeTextFile(completionMarker, '');

            return {
                success: true,
                message: '离线依赖包安装成功'
            };
        } catch (error) {
            return {
                success: false,
                message: `离线安装依赖包时出错: ${error}`
            };
        }
    }

    async cleanupOfflinePackage(installDir: string): Promise<void> {
        try {
            const extractDir = await this.offlineExtractDir(installDir);
            if (await exists(extractDir)) {
                await remove(extractDir, { recursive: true });
            }
        } catch (cleanupError) {
            console.warn('清理离线解压目录失败(忽略):', cleanupError);
        }
    }

    async saveSettings(installConfig: {
        path: string;
        version: string;
        platform: string;
        enableGPU?: boolean;
        enableAutoUpdate?: boolean;
    }): Promise<void> {

        const tarPath = await resolveResource('resources/app.tar.gz');
        const output = await invoke('unpack_app', {
            tar_path: tarPath,
            target_path: installConfig.path
        });
        console.log('解压完成: ' + output);

        const extensionsPath = await resolveResource('resources/extensions');
        const entries = await readDir(extensionsPath);
        console.log(entries);
        const extensionInstallPath = await join(installConfig.path, 'extensions');
        for (const entry of entries) {
            const output = await invoke('unpack_app', {
                tar_path: await join(extensionsPath, entry.name),
                target_path: extensionInstallPath
            });
            console.log('解压插件完成: ' + output);
        }

        const store = await load('settings.json', { autoSave: false });
        await store.set('root', installConfig);
        await store.save();
    }
} 