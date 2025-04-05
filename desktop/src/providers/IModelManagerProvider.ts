/**
 * 模型项接口
 */
export interface ModelItem {
  id: string;
  name: string;
  description: string;
  tags: string[];
}

/**
 * 模型组接口
 */
export interface ModelGroup {
  id: string;
  name: string;
  models: ModelItem[];
  isOpen: boolean;
}

/**
 * 模型管理提供者接口
 */
export interface IModelManagerProvider {
  /**
   * 获取所有模型组
   */
  getModelGroups(): Promise<ModelGroup[]>;
  
  /**
   * 获取所有可用标签
   */
  getAllTags(): Promise<string[]>;
  
  /**
   * 搜索模型
   * @param query 搜索关键词
   * @param tags 筛选标签
   */
  searchModels(query: string, tags: string[]): Promise<ModelGroup[]>;
  
  /**
   * 删除模型
   * @param groupId 组ID
   * @param modelId 模型ID
   */
  deleteModel(groupId: string, modelId: string): Promise<boolean>;
  
  /**
   * 添加模型
   * @param model 模型信息
   * @param groupId 目标组ID
   */
  addModel(model: ModelItem, groupId: string): Promise<boolean>;
  
  /**
   * 切换组的展开状态
   * @param groupId 组ID
   * @param isOpen 是否展开
   */
  toggleGroupOpen(groupId: string, isOpen: boolean): Promise<boolean>;
} 