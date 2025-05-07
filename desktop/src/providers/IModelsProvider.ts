/**
 * 模型数据接口
 */
export interface Model {
  id: string;
  name: string;
  path: string;
  type: string;
  size: string;
  installed: boolean;
}

/**
 * 监听目录接口
 */
export interface WatchedDirectory {
  id: string;
  path: string;
}

/**
 * 模型服务提供者接口
 */
export interface ModelsProvider {
  /**
   * 从文件系统选择目录
   * @returns 返回选中的目录路径
   */
  selectDirectory(): Promise<string>;
  
  /**
   * 扫描指定目录中的模型
   * @param directoryPath 目录路径
   * @param onModelFound 当找到模型时的回调函数
   * @returns 扫描到的模型列表
   */
  scanDirectory(directoryPath: string, onModelFound?: (model: Model) => void): Promise<Model[]>;
  
  /**
   * 添加模型到系统
   * @param modelPath 模型路径
   * @returns 是否添加成功
   */
  addModel(modelPath: string): Promise<boolean>;
  
  /**
   * 获取所有监听目录
   * @returns 监听目录列表
   */
  getWatchedDirectories(): Promise<WatchedDirectory[]>;
  
  /**
   * 添加监听目录
   * @param directoryPath 目录路径
   * @returns 新添加的监听目录
   */
  addWatchedDirectory(directoryPath: string): Promise<WatchedDirectory>;
  
  /**
   * 移除监听目录
   * @param directoryId 监听目录ID
   * @returns 是否移除成功
   */
  removeWatchedDirectory(directoryId: string): Promise<boolean>;
  
  /**
   * 获取拖放的文件路径
   * @param event 拖放事件
   * @returns 文件路径
   */
  getDroppedFilePath(event: React.DragEvent): Promise<string>;
} 