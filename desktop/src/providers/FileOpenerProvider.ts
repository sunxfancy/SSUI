import { Message } from "ssui_components";
import GlobalStateManager from "../services/GlobalState";
import { basename } from "@tauri-apps/api/path";

// 定义API返回的数据类型
type OpenerTemplate = [string, string, string]; // [名称, 前缀, 后缀]
type OpenersByExtension = Record<string, OpenerTemplate[]>;

export class FileOpenerProvider {
  private message: Message;
  private openersCache: OpenersByExtension | null = null;
  private isLoading: boolean = false;

  // 单例实例
  private static instance: FileOpenerProvider | null = null;

  // 私有构造函数，防止外部直接实例化
  private constructor() {
    const rootState = GlobalStateManager.getInstance().getRootState();
    this.message = new Message(rootState?.host || "localhost", rootState?.port || 7420);
  }

  /**
   * 获取FileOpenerProvider的单例实例
   */
  public static getInstance(): FileOpenerProvider {
    if (!FileOpenerProvider.instance) {
      FileOpenerProvider.instance = new FileOpenerProvider();
    }
    return FileOpenerProvider.instance;
  }

  /**
   * 懒加载方式获取打开器配置
   * 只有在第一次调用时才会从API获取数据
   */
  private async loadOpenersConfig(): Promise<OpenersByExtension> {
    // 如果已经在加载中，等待加载完成
    if (this.isLoading) {
      await new Promise<void>((resolve) => {
        const checkInterval = setInterval(() => {
          if (!this.isLoading) {
            clearInterval(checkInterval);
            resolve();
          }
        }, 100);
      });
      return this.openersCache!;
    }

    // 如果已经有缓存，直接返回
    if (this.openersCache) {
      return this.openersCache;
    }

    // 开始加载
    this.isLoading = true;
    try {
      console.log("正在从API获取文件打开器配置...");
      const result = await this.message.get("config/opener");

      if (result && typeof result === 'object') {
        this.openersCache = result as OpenersByExtension;
        return this.openersCache;
      }

      console.error("获取文件打开器配置失败: 返回数据格式不正确");
      return {};
    } catch (error) {
      console.error("获取文件打开器配置失败:", error);
      return {};
    } finally {
      this.isLoading = false;
    }
  }

  /**
   * 获取指定文件扩展名的所有可用打开器
   */
  public static async getOpenersForExtension(filePath: string): Promise<Array<OpenerTemplate>> {
    const extension = '.' + filePath.split('.').pop();
    const name = await basename(filePath);
    const openersConfig = await this.getInstance().loadOpenersConfig();

    // 获取该扩展名的所有打开器模板
    const templates = openersConfig[extension] || openersConfig[name] || [];

    // 转换为前端需要的格式
    return templates;
  }

  /**
   * 使用指定的打开器构造打开文件的URL
   */
  public static async constructOpenUrl(openerName: string, filePath: string): Promise<string> {
    const openers = await this.getOpenersForExtension(filePath);

    // 查找匹配的打开器
    const opener = openers.find(o => o[0] === openerName);
    if (!opener) {
      throw new Error(`找不到名为 "${openerName}" 的打开器`);
    }

    // 替换模板中的占位符
    return opener[1] + filePath + opener[2];
  }

  public static async constructDefaultUrl(filePath: string): Promise<string> {
    const openers = await this.getOpenersForExtension(filePath);
    if (openers && openers.length > 0) {
      return openers[0][1] + filePath + openers[0][2];
    }
    throw new Error(`找不到默认打开器: ${filePath}`);
  }
}

// 导出默认实例，方便直接使用
export default FileOpenerProvider;
