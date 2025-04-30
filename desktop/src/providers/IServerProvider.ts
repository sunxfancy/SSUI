import { CommandInfo } from './IInstallerProvider';

export interface IServerProvider {
  // 启动 server 包
  startServer(): Promise<CommandInfo>;
  
  // 停止 server 包
  stopServer(): Promise<CommandInfo>;
  
  // 获取服务器状态
  getServerStatus(): Promise<CommandInfo>;
  
  // 重启服务器
  restartServer(): Promise<CommandInfo>;
} 