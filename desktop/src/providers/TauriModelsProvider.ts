import { Model, ModelsProvider, WatchedDirectory } from "./IModelsProvider";
import { open } from '@tauri-apps/plugin-dialog';
import { Message } from "ssui_components";

export class TauriModelsProvider implements ModelsProvider {
    private message: Message;

    constructor() {
        this.message = new Message("localhost", 7420);
    }

      /**
   * 从文件系统选择目录
   * @returns 返回选中的目录路径
   */
  async selectDirectory(): Promise<string> {
    try {
      const result = await open({
        directory: true,
        multiple: false,
      });
      return result ? result as string : '';
    } catch (error) {
      console.error("选择目录失败:", error);
      throw error;
    }
  }
  
  /**
   * 扫描指定目录中的模型
   * @param directoryPath 目录路径
   * @param onModelFound 当找到模型时的回调函数
   * @returns 扫描到的模型列表
   */
  async scanDirectory(directoryPath: string, onModelFound?: (model: Model) => void): Promise<Model[]> {
    const models: Model[] = [];
    
    await this.message.post("config/scan_models", {
      "scan_dir": directoryPath
    }, {
      "find_model": (data: any) => {
        console.log("find_model: ", data);
        // 将找到的模型添加到列表中
        if (data && data.path && data.name) {
          const model: Model = {
            id: Date.now().toString() + Math.random().toString(36).substr(2, 9), // 生成唯一ID
            name: data.name,
            path: data.path,
            type: data.type || "未知类型",
            size: data.size || "未知大小"
          };
          models.push(model);
          
          // 如果提供了回调函数，则调用它
          if (onModelFound) {
            onModelFound(model);
          }
        }
      },
    });
    
    return models;
  }
  
  /**
   * 添加模型到系统
   * @param modelPath 模型路径
   * @returns 是否添加成功
   */
  addModel(modelPath: string): Promise<boolean> {
    return Promise.resolve(false);
  }
  
  /**
   * 获取所有监听目录
   * @returns 监听目录列表
   */
  getWatchedDirectories(): Promise<WatchedDirectory[]> {
    return Promise.resolve([]);
  }
  
  /**
   * 添加监听目录
   * @param directoryPath 目录路径
   * @returns 新添加的监听目录
   */
  addWatchedDirectory(directoryPath: string): Promise<WatchedDirectory> {
    return Promise.resolve({ id: '', path: directoryPath });
  }
  
  /**
   * 移除监听目录
   * @param directoryId 监听目录ID
   * @returns 是否移除成功
   */
  removeWatchedDirectory(directoryId: string): Promise<boolean> {
    return Promise.resolve(false);
  }
  
  /**
   * 获取拖放的文件路径
   * @param event 拖放事件
   * @returns 文件路径
   */
  getDroppedFilePath(event: React.DragEvent): Promise<string> {
    return Promise.resolve('');
  }
}
