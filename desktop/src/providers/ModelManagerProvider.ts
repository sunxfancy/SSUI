import GlobalStateManager from "../services/GlobalState";
import { IModelManagerProvider, ModelGroup, ModelItem } from "./IModelManagerProvider";
import { Message } from "ssui_components";

export class ModelManagerProvider implements IModelManagerProvider {
    private message: Message;
    private modelGroups: ModelGroup[] = [];
    private maxRetries: number = 10; // 最大重试次数

    constructor() {
        const rootState = GlobalStateManager.getInstance().getRootState();
        this.message = new Message(rootState?.host || "localhost", rootState?.port || 7420);
    }

    /**
     * 获取所有模型组
     */
    async getModelGroups(): Promise<ModelGroup[]> {
        let retryCount = 0;
        
        while (retryCount < this.maxRetries) {
            try {
                // 从服务器获取已安装的模型
                const response = await this.message.get("api/available_models");
                
                if (response && Array.isArray(response)) {
                    // 按标签分组模型
                    const groupsMap = new Map<string, ModelGroup>();
                    
                    // 处理每个模型
                    response.forEach((item: any) => {
                        // 获取模型的主要标签（第一个标签）
                        const mainTag = item.tags && item.tags.length > 0 ? item.tags[0] : "其他";
                        
                        // 创建模型项
                        const modelItem: ModelItem = {
                            id: item.path, // 使用路径作为ID
                            name: item.name,
                            description: item.description || "无描述",
                            tags: item.tags || []
                        };
                        
                        // 检查是否已存在该标签的组
                        if (!groupsMap.has(mainTag)) {
                            // 创建新组
                            groupsMap.set(mainTag, {
                                id: mainTag,
                                name: mainTag,
                                models: [],
                                isOpen: false
                            });
                        }
                        
                        // 将模型添加到对应组
                        const group = groupsMap.get(mainTag)!;
                        group.models.push(modelItem);
                    });
                    
                    // 转换为数组
                    this.modelGroups = Array.from(groupsMap.values());
                    return this.modelGroups; // 成功获取数据，直接返回
                }
                
                // 如果响应不是数组，也视为失败
                throw new Error("响应格式不正确");
            } catch (error) {
                console.error(`获取模型组失败 (尝试 ${retryCount + 1}/${this.maxRetries}):`, error);
                retryCount++;
                
                if (retryCount < this.maxRetries) {
                    console.log(`将在3秒后重试...`);
                    await new Promise(resolve => setTimeout(resolve, 3000)); // 等待3秒后重试
                } else {
                    console.error("已达到最大重试次数，获取模型组失败");
                    return []; // 达到最大重试次数，返回空数组
                }
            }
        }
        
        return []; // 默认返回空数组
    }
    
    /**
     * 获取所有可用标签
     */
    async getAllTags(): Promise<string[]> {
        const allTags = Array.from(new Set(this.modelGroups.flatMap(group => 
            group.models.flatMap(model => model.tags)
        )));
        return allTags;
    }
    
    /**
     * 搜索模型
     * @param query 搜索关键词
     * @param tags 筛选标签
     */
    async searchModels(query: string, tags: string[]): Promise<ModelGroup[]> {
        return this.modelGroups.map(group => {
          // 过滤每个组中的模型
          const filteredModels = group.models.filter(model => {
            // 搜索过滤
            const matchesSearch = 
              model.name.toLowerCase().includes(query.toLowerCase()) || 
              model.description.toLowerCase().includes(query.toLowerCase());
            
            // 标签过滤
            const matchesTags = 
              tags.length === 0 || 
              tags.some(tag => model.tags.includes(tag));
            
            return matchesSearch && matchesTags;
          });
          
          // 返回带有过滤后模型的组
          return {
            ...group,
            models: filteredModels
          };
        }).filter(group => group.models.length > 0); // 只保留有模型的组
    }
    
    /**
     * 删除模型
     * @param groupId 组ID
     * @param modelId 模型ID
     */
    async deleteModel(groupId: string, modelId: string): Promise<boolean> {
        const groupIndex = this.modelGroups.findIndex(group => group.id === groupId);
        if (groupIndex === -1) return false;
        
        const originalLength = this.modelGroups[groupIndex].models.length;
        this.modelGroups[groupIndex].models = this.modelGroups[groupIndex].models.filter(
            model => model.id !== modelId
        );

        try {
            // 这里应该调用服务器的API来删除模型
            // 由于服务器API可能没有直接删除模型的功能，这里只是模拟
            console.log(`删除模型: 组=${groupId}, 模型=${modelId}`);
        } catch (error) {
            console.error("删除模型失败:", error);
            return false;
        }
        
        return this.modelGroups[groupIndex].models.length < originalLength;
        
    }
    
    /**
     * 添加模型
     * @param model 模型信息
     * @param groupId 目标组ID
     */
    async addModel(model: ModelItem, groupId: string): Promise<boolean> {
        const groupIndex = this.modelGroups.findIndex(group => group.id === groupId);
        if (groupIndex === -1) return false;
        
        this.modelGroups[groupIndex].models.push(model);
        return true;
    }
    
    /**
     * 切换组的展开状态
     * @param groupId 组ID
     * @param isOpen 是否展开
     */
    async toggleGroupOpen(groupId: string, isOpen: boolean): Promise<boolean> {
        try {
            // 更新本地状态
            const groupIndex = this.modelGroups.findIndex(group => group.id === groupId);
            if (groupIndex === -1) return false;
            
            this.modelGroups[groupIndex].isOpen = isOpen;
            return true;
        } catch (error) {
            console.error("切换组展开状态失败:", error);
            return false;
        }
    }
} 