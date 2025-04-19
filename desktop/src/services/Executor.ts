import { TauriExecutorProvider } from '../providers/TauriExecutorProvider';
import { CommandInfo } from '../providers/IInstallerProvider';

/**
 * 执行器服务类
 * 用于管理 ss_executor 包的启动、停止和状态查询
 */
class ExecutorService {
  private static instance: ExecutorService;
  private executorProvider: TauriExecutorProvider;

  private constructor() {
    this.executorProvider = new TauriExecutorProvider();
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): ExecutorService {
    if (!ExecutorService.instance) {
      ExecutorService.instance = new ExecutorService();
    }
    return ExecutorService.instance;
  }

  /**
   * 启动执行器
   */
  public async startExecutor(): Promise<CommandInfo> {
    return await this.executorProvider.startExecutor();
  }

  /**
   * 停止执行器
   */
  public async stopExecutor(): Promise<CommandInfo> {
    return await this.executorProvider.stopExecutor();
  }

  /**
   * 获取执行器状态
   */
  public async getExecutorStatus(): Promise<CommandInfo> {
    return await this.executorProvider.getExecutorStatus();
  }
}

export default ExecutorService;
