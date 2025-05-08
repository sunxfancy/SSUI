import { Model, ModelsProvider, WatchedDirectory } from '../providers/IModelsProvider';

/**
 * 模拟数据的模型服务提供者
 */
export class MockModelsProvider implements ModelsProvider {
  private watchedDirectories: WatchedDirectory[] = [];
  
  async selectDirectory(): Promise<string> {
    // 模拟用户选择了一个目录
    return "/用户选择的目录路径";
  }
  
  async scanDirectory(directoryPath: string): Promise<Model[]> {
    // 模拟扫描过程
    // 实际应用中需要遍历目录找模型文件
    return new Promise(resolve => {
      setTimeout(() => {
        const mockModels: Model[] = [
          { 
            id: '1', 
            name: 'GPT-2', 
            path: `${directoryPath}/gpt2`, 
            type: 'LLM', 
            size: '548 MB',
            installed: false
          },
          { 
            id: '2', 
            name: 'StableDiffusion v1.5', 
            path: `${directoryPath}/sd_v1_5`, 
            type: 'Diffusion', 
            size: '4.27 GB',
            installed: false
          },
          { 
            id: '3', 
            name: 'BERT', 
            path: `${directoryPath}/bert`, 
            type: 'Encoder', 
            size: '420 MB',
            installed: false
          }
        ];
        
        resolve(mockModels);
      }, 1500);
    });
  }
  
  async addModel(modelPath: string): Promise<boolean> {
    // 模拟添加模型过程
    console.log(`添加模型: ${modelPath}`);
    return true;
  }
  
  async getWatchedDirectories(): Promise<WatchedDirectory[]> {
    // 返回储存的监听目录
    return this.watchedDirectories;
  }
  
  async addWatchedDirectory(directoryPath: string): Promise<WatchedDirectory> {
    const newWatchedDir: WatchedDirectory = {
      id: Date.now().toString(),
      path: directoryPath
    };
    
    this.watchedDirectories.push(newWatchedDir);
    return newWatchedDir;
  }
  
  async removeWatchedDirectory(directoryId: string): Promise<boolean> {
    const initialLength = this.watchedDirectories.length;
    this.watchedDirectories = this.watchedDirectories.filter(dir => dir.id !== directoryId);
    
    return this.watchedDirectories.length !== initialLength;
  }
  
  async getDroppedFilePath(event: React.DragEvent): Promise<string> {
    // 模拟从拖放事件中获取文件路径
    const files = event.dataTransfer.files;
    if (files && files.length > 0) {
      // 在实际应用中，这可能需要通过Electron API来获取
      // 这里我们假设有一个path属性或者通过files[0].path访问
      return "/拖放的目录路径";
    }
    throw new Error("No file dropped");
  }
} 