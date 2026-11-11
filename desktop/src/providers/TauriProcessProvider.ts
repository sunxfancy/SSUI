import { invoke } from '@tauri-apps/api/core';
import { join } from '@tauri-apps/api/path';
import { platform } from '@tauri-apps/plugin-os';
import GlobalStateManager from '../services/GlobalState';
import type { CommandInfo } from './IInstallerProvider';

export interface ProcessEnvironment {
  initialize(): Promise<void>;
  rootPath(): string | null;
  pythonPath(root: string): Promise<string>;
}

const defaultEnvironment: ProcessEnvironment = {
  initialize: () => GlobalStateManager.getInstance().initialize(),
  rootPath: () => GlobalStateManager.getInstance().getRootPath(),
  pythonPath: async root => join(root, platform() === 'windows' ? '.venv/Scripts/python.exe' : '.venv/bin/python'),
};

interface ProcessStatus { is_running: boolean; pid: string | null }

/** Shared IPC contract for server and executor, with one mutation at a time. */
export class TauriProcessProvider {
  private pending = false;

  constructor(private kind: 'server' | 'executor', private label: string,
    private environment: ProcessEnvironment = defaultEnvironment) {}

  private async change(action: 'start' | 'restart' | 'stop'): Promise<CommandInfo> {
    if (this.pending) return { success: false, message: `${this.label}操作正在进行中` };
    this.pending = true;
    try {
      if (action === 'stop') {
        const stopped = await invoke<boolean>(`stop_${this.kind}`);
        if (!stopped) return { success: false, message: `${this.label}未在运行中` };
        return { success: true, message: `${this.label}已停止` };
      }
      await this.environment.initialize();
      const cwd = this.environment.rootPath();
      if (!cwd) return { success: false, message: '未找到安装路径，请先完成安装' };
      const path = await this.environment.pythonPath(cwd);
      const result = await invoke<{ pid: string }>(`${action}_${this.kind}`, { path, cwd });
      if (!result || typeof result.pid !== 'string' || !/^[1-9]\d*$/.test(result.pid)) {
        throw new Error('无效的进程 ID');
      }
      return { success: true, message: `${this.label}${action === 'start' ? '启动' : '重启'}成功，进程 ID: ${result.pid}` };
    } catch (error) {
      return { success: false, message: `${this.label}操作失败: ${error}` };
    } finally {
      this.pending = false;
    }
  }

  start() { return this.change('start'); }
  stop() { return this.change('stop'); }
  restart() { return this.change('restart'); }

  async status(): Promise<CommandInfo> {
    try {
      const status = await invoke<ProcessStatus>(`get_${this.kind}_status`);
      if (!status || typeof status.is_running !== 'boolean' ||
        (status.is_running && (typeof status.pid !== 'string' || !/^[1-9]\d*$/.test(status.pid)))) {
        throw new Error('无效的进程状态');
      }
      return { success: true, message: status.is_running
        ? `${this.label}正在运行中，进程 ID: ${status.pid}` : `${this.label}未在运行中` };
    } catch (error) {
      return { success: false, message: `检查${this.label}状态时出错: ${error}` };
    }
  }
}
