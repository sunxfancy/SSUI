import { TauriServerProvider } from '../providers/TauriServerProvider';
import { CommandInfo } from '../providers/IInstallerProvider';

/**
 * 服务器服务类
 * 用于管理 server 包的启动、停止和状态查询
 */
class ServerService {
  private static instance: ServerService;
  private serverProvider: TauriServerProvider;

  private constructor() {
    this.serverProvider = new TauriServerProvider();
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): ServerService {
    if (!ServerService.instance) {
      ServerService.instance = new ServerService();
    }
    return ServerService.instance;
  }

  /**
   * 启动服务器
   */
  public async startServer(): Promise<CommandInfo> {
    return await this.serverProvider.startServer();
  }

  /**
   * 停止服务器
   */
  public async stopServer(): Promise<CommandInfo> {
    return await this.serverProvider.stopServer();
  }

  /**
   * 获取服务器状态
   */
  public async getServerStatus(): Promise<CommandInfo> {
    return await this.serverProvider.getServerStatus();
  }
}

export default ServerService;
