import { IExtensionsProvider } from './IExtensionsProvider';
import { ExtensionItem } from '../components/Extensions';
import { Message } from "ssui_components";
import GlobalStateManager from "../services/GlobalState";
import { IconName } from '@blueprintjs/icons';

interface ExtensionData {
  name: string;
  path: string;
  version: string;
  disabled?: boolean;
  server: {
    venv: string;
    dependencies: string[];
    main: string;
  };
  web_ui: {
    dist: string;
  };
}

interface ExtensionsResponse {
  [key: string]: ExtensionData;
}

export class ExtensionsProvider implements IExtensionsProvider {
  private message: Message;

  constructor() {
    const rootState = GlobalStateManager.getInstance().getRootState();
    this.message = new Message(rootState?.host || "localhost", rootState?.port || 7420);
  }

  async getExtensions(): Promise<ExtensionItem[]> {
    try {
      const result = await this.message.get("api/extensions");
      
      if (result && typeof result === 'object') {
        const extensionsData = result as ExtensionsResponse;
        return this.convertToExtensionItems(extensionsData);
      }
      
      return [];
    } catch (error) {
      console.error("获取扩展列表失败:", error);
      return [];
    }
  }

  async installExtension(extensionId: string): Promise<boolean> {
    try {
      const result = await this.message.post("api/extensions/install", {
        extension_id: extensionId
      });
      
      return result && result.type === "success";
    } catch (error) {
      console.error("安装扩展失败:", error);
      return false;
    }
  }

  async uninstallExtension(extensionId: string): Promise<boolean> {
    try {
      const result = await this.message.post("api/extensions/uninstall", {
        extension_id: extensionId
      });
      
      return result && result.type === "success";
    } catch (error) {
      console.error("卸载扩展失败:", error);
      return false;
    }
  }

  async disableExtension(extensionId: string): Promise<boolean> {
    try {
      const result = await this.message.post("api/extensions/disable", {
        extension_id: extensionId
      });
      
      return result && result.type === "success";
    } catch (error) {
      console.error("禁用扩展失败:", error);
      return false;
    }
  }

  async enableExtension(extensionId: string): Promise<boolean> {
    try {
      const result = await this.message.post("api/extensions/enable", {
        extension_id: extensionId
      });
      
      return result && result.type === "success";
    } catch (error) {
      console.error("启用扩展失败:", error);
      return false;
    }
  }

  async searchExtensions(query: string): Promise<ExtensionItem[]> {
      return [];
  }

  private convertToExtensionItems(data: ExtensionsResponse): ExtensionItem[] {
    return Object.entries(data).map(([id, ext]) => {
      return {
        id: id,
        name: ext.name,
        description: `版本: ${ext.version}`,
        author: "SSUI",
        version: ext.version,
        icon: this.getIconForExtension(id),
        tags: this.getTagsForExtension(id),
        installed: true, // 假设所有已加载的扩展都已安装
        featured: this.isFeaturedExtension(id),
        disabled: ext.disabled || false // 添加禁用状态
      };
    });
  }

  private getIconForExtension(id: string): IconName {
    // 根据扩展ID返回对应的图标
    const iconMap: Record<string, IconName> = {
      "3D-Model": "cube",
      "Audio": "music",
      "ExampleExtension": "help",
      "ImageExtension": "media",
      "LLM": "code",
      "Motion": "walk",
      "Video": "video",
      "Voice": "microphone"
    };
    
    return iconMap[id] || "extension";
  }

  private getTagsForExtension(id: string): string[] {
    // 根据扩展ID返回对应的标签
    const tagMap: Record<string, string[]> = {
      "3D-Model": ["3D", "模型"],
      "Audio": ["音频", "声音"],
      "ExampleExtension": ["示例"],
      "ImageExtension": ["图像", "图片"],
      "LLM": ["AI", "语言模型"],
      "Motion": ["动作", "运动"],
      "Video": ["视频", "媒体"],
      "Voice": ["语音", "声音"]
    };
    
    return tagMap[id] || [];
  }

  private isFeaturedExtension(id: string): boolean {
    // 定义精选扩展
    const featuredExtensions = ["LLM", "ImageExtension", "Video"];
    return featuredExtensions.includes(id);
  }
}
