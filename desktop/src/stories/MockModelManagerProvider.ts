import { IModelManagerProvider, ModelGroup, ModelItem } from '../providers/IModelManagerProvider';

/**
 * 模拟数据的模型管理提供者
 */
export class MockModelManagerProvider implements IModelManagerProvider {
  private modelGroups: ModelGroup[];
  
  constructor() {
    // 示例数据 - 按组分类
    this.modelGroups = [
      { 
        id: "checkpoint", 
        name: "Checkpoint", 
        isOpen: false,
        models: [
          { id: "sd1-v1-5", name: "Stable Diffusion 1.5", description: "基础SD1.5模型", tags: ["sd1"] },
          { id: "sd2-v2-1", name: "Stable Diffusion 2.1", description: "改进版SD2.1模型", tags: ["sd2"] },
          { id: "sdxl-base", name: "SDXL Base", description: "大规模SDXL基础模型", tags: ["sdxl"] },
        ] 
      },
      { 
        id: "vae", 
        name: "VAE", 
        isOpen: false,
        models: [
          { id: "vae-ft-mse", name: "VAE FT-MSE", description: "优化的VAE编码器", tags: ["sd1", "sd2"] },
          { id: "vae-sdxl", name: "VAE SDXL", description: "SDXL专用VAE", tags: ["sdxl"] },
        ] 
      },
      { 
        id: "lora", 
        name: "LoRA", 
        isOpen: false,
        models: [
          { id: "lora-anime", name: "Anime Style", description: "动漫风格LoRA", tags: ["sd1", "sd2"] },
          { id: "lora-realistic", name: "Realistic", description: "写实风格LoRA", tags: ["sd1", "sdxl"] },
          { id: "lora-flux", name: "Flux Style", description: "Flux引擎专用LoRA", tags: ["flux1"] },
        ] 
      },
      { 
        id: "clip", 
        name: "CLIP", 
        isOpen: false,
        models: [
          { id: "clip-vit-large", name: "ViT-L/14", description: "大型CLIP视觉编码器", tags: ["sd2", "sdxl"] },
          { id: "clip-vit-base", name: "ViT-B/32", description: "基础CLIP视觉编码器", tags: ["sd1"] },
        ] 
      },
      { 
        id: "controlnet", 
        name: "ControlNet", 
        isOpen: false,
        models: [
          { id: "cn-canny", name: "Canny Edge", description: "边缘检测控制网络", tags: ["sd1", "sd2"] },
          { id: "cn-depth", name: "Depth", description: "深度图控制网络", tags: ["sd1", "sdxl"] },
          { id: "cn-pose", name: "Pose", description: "姿势控制网络", tags: ["sd2", "flux1"] },
        ] 
      },
    ];
  }
  
  async getModelGroups(): Promise<ModelGroup[]> {
    return [...this.modelGroups];
  }
  
  async getAllTags(): Promise<string[]> {
    // 从所有模型中提取标签
    const allTags = Array.from(new Set(this.modelGroups.flatMap(group => 
      group.models.flatMap(model => model.tags)
    )));
    return allTags;
  }
  
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
  
  async deleteModel(groupId: string, modelId: string): Promise<boolean> {
    const groupIndex = this.modelGroups.findIndex(group => group.id === groupId);
    if (groupIndex === -1) return false;
    
    const originalLength = this.modelGroups[groupIndex].models.length;
    this.modelGroups[groupIndex].models = this.modelGroups[groupIndex].models.filter(
      model => model.id !== modelId
    );
    
    return this.modelGroups[groupIndex].models.length < originalLength;
  }
  
  async addModel(model: ModelItem, groupId: string): Promise<boolean> {
    const groupIndex = this.modelGroups.findIndex(group => group.id === groupId);
    if (groupIndex === -1) return false;
    
    this.modelGroups[groupIndex].models.push(model);
    return true;
  }
  
  async toggleGroupOpen(groupId: string, isOpen: boolean): Promise<boolean> {
    const groupIndex = this.modelGroups.findIndex(group => group.id === groupId);
    if (groupIndex === -1) return false;
    
    this.modelGroups[groupIndex].isOpen = isOpen;
    return true;
  }
} 