import { CommandInfo } from './IInstallerProvider';

export interface IExecutorProvider {
  // 启动 ss_executor 包
  startExecutor(): Promise<CommandInfo>;
  
  // 停止 ss_executor 包
  stopExecutor(): Promise<CommandInfo>;
  
  // 获取执行器状态
  getExecutorStatus(): Promise<CommandInfo>;
} 