import { platform } from '@tauri-apps/plugin-os';
import { join } from '@tauri-apps/api/path';
import { invoke } from '@tauri-apps/api/core';
import { IExecutorProvider } from './IExecutorProvider';
import { CommandInfo } from './IInstallerProvider';
import GlobalStateManager from '../services/GlobalState';

export class TauriExecutorProvider implements IExecutorProvider {
  private processId: number | null = null;
  private isRunning: boolean = false;

  constructor() {
    // 初始化全局状态
    GlobalStateManager.getInstance().initialize().catch(error => {
      console.error('初始化全局状态失败:', error);
    });
  }

  /**
   * 启动 ss_executor 包
   */
  async startExecutor(): Promise<CommandInfo> {
    if (this.isRunning) {
      return {
        success: false,
        message: '执行器已经在运行中'
      };
    }

    try {
      const rootPath = GlobalStateManager.getInstance().getRootPath();
      if (!rootPath) {
        return {
          success: false,
          message: '未找到安装路径，请先完成安装'
        };
      }

      const currentPlatform = await platform();
      const pythonPath = await join(rootPath, currentPlatform === 'windows' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python');

      // 启动 ss_executor 包
      const result: any = await invoke('start_executor', {
        path: pythonPath,
        cwd: rootPath,
      });

      // 假设返回的结果中包含进程 ID
      if (result && result.pid) {
        this.processId = result.pid;
        this.isRunning = true;
        return {
          success: true,
          message: `执行器启动成功，进程 ID: ${this.processId}`
        };
      } else {
        return {
          success: false,
          message: '启动执行器失败，未获取到进程 ID'
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `启动执行器时出错: ${error}`
      };
    }
  }

  /**
   * 停止 ss_executor 包
   */
  async stopExecutor(): Promise<CommandInfo> {
    if (!this.isRunning || !this.processId) {
      return {
        success: false,
        message: '执行器未在运行中'
      };
    }

    try {
      // 终止进程
      await invoke('kill_process', {
        pid: this.processId
      });

      this.processId = null;
      this.isRunning = false;

      return {
        success: true,
        message: '执行器已停止'
      };
    } catch (error) {
      return {
        success: false,
        message: `停止执行器时出错: ${error}`
      };
    }
  }

  /**
   * 获取执行器状态
   */
  async getExecutorStatus(): Promise<CommandInfo> {
    if (!this.isRunning || !this.processId) {
      return {
        success: true,
        message: '执行器未在运行中'
      };
    }

    try {
      // 检查进程是否仍在运行
      const isAlive = await invoke('get_executor_status');

      if (isAlive) {
        return {
          success: true,
          message: `执行器正在运行中，进程 ID: ${this.processId}`
        };
      } else {
        // 进程已终止，更新状态
        this.processId = null;
        this.isRunning = false;
        return {
          success: true,
          message: '执行器已终止'
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `检查执行器状态时出错: ${error}`
      };
    }
  }
} 