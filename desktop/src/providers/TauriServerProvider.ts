import { platform } from '@tauri-apps/plugin-os';
import { join } from '@tauri-apps/api/path';
import { invoke } from '@tauri-apps/api/core';
import { IServerProvider } from './IServerProvider';
import { CommandInfo } from './IInstallerProvider';
import GlobalStateManager from '../services/GlobalState';

export class TauriServerProvider implements IServerProvider {
  private processId: number | null = null;
  private isRunning: boolean = false;

  constructor() {
    // 初始化全局状态
    GlobalStateManager.getInstance().initialize().catch(error => {
      console.error('初始化全局状态失败:', error);
    });
  }

  /**
   * 启动 server 包
   */
  async startServer(): Promise<CommandInfo> {
    if (this.isRunning) {
      return {
        success: false,
        message: '服务器已经在运行中'
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

      // 启动 server 包
      const result: any = await invoke('start_server', {
        path: pythonPath,
        cwd: rootPath,
      });

      // 假设返回的结果中包含进程 ID
      if (result && result.pid) {
        this.processId = result.pid;
        this.isRunning = true;
        return {
          success: true,
          message: `服务器启动成功，进程 ID: ${this.processId}`
        };
      } else {
        return {
          success: false,
          message: '启动服务器失败，未获取到进程 ID'
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `启动服务器时出错: ${error}`
      };
    }
  }

  /**
   * 停止 server 包
   */
  async stopServer(): Promise<CommandInfo> {
    if (!this.isRunning || !this.processId) {
      return {
        success: false,
        message: '服务器未在运行中'
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
        message: '服务器已停止'
      };
    } catch (error) {
      return {
        success: false,
        message: `停止服务器时出错: ${error}`
      };
    }
  }

  /**
   * 获取服务器状态
   */
  async getServerStatus(): Promise<CommandInfo> {
    if (!this.isRunning || !this.processId) {
      return {
        success: true,
        message: '服务器未在运行中'
      };
    }

    try {
      // 检查进程是否仍在运行
      const isAlive = await invoke('get_server_status');

      if (isAlive) {
        return {
          success: true,
          message: `服务器正在运行中，进程 ID: ${this.processId}`
        };
      } else {
        // 进程已终止，更新状态
        this.processId = null;
        this.isRunning = false;
        return {
          success: true,
          message: '服务器已终止'
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `检查服务器状态时出错: ${error}`
      };
    }
  }
  
  /**
   * 重启服务器
   */
  async restartServer(): Promise<CommandInfo> {
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

      // 调用重启服务
      const result: any = await invoke('restart_server', {
        path: pythonPath,
        cwd: rootPath,
      });

      // 假设返回的结果中包含进程 ID
      if (result && result.pid) {
        this.processId = result.pid;
        this.isRunning = true;
        return {
          success: true,
          message: `服务器重启成功，进程 ID: ${this.processId}`
        };
      } else {
        return {
          success: false,
          message: '重启服务器失败，未获取到进程 ID'
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `重启服务器时出错: ${error}`
      };
    }
  }
} 