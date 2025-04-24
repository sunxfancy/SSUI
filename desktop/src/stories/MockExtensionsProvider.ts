import { IExtensionsProvider } from '../providers/IExtensionsProvider';
import { ExtensionItem } from '../components/Extensions';

export class MockExtensionsProvider implements IExtensionsProvider {
  private extensions: ExtensionItem[] = [
    {
      id: 'ext1',
      name: '数据可视化',
      description: '提供多种数据可视化图表和工具',
      author: 'DataViz团队',
      version: '1.2.0',
      icon: 'chart',
      tags: ['可视化', '图表'],
      installed: true
    },
    {
      id: 'ext2',
      name: '高级统计分析',
      description: '提供高级统计分析功能和算法',
      author: 'Stats Pro',
      version: '2.1.3',
      icon: 'calculator',
      tags: ['统计', '分析'],
      installed: true
    },
    {
      id: 'ext3',
      name: '数据清洗工具',
      description: '自动检测和修复数据问题',
      author: 'CleanData',
      version: '1.0.5',
      icon: 'clean',
      tags: ['数据处理', '清洗'],
      installed: false,
      featured: true
    },
    {
      id: 'ext4',
      name: '机器学习模型库',
      description: '预训练模型和算法集合',
      author: 'ML Community',
      version: '3.2.1',
      icon: 'learning',
      tags: ['机器学习', 'AI'],
      installed: false,
      featured: true
    },
    {
      id: 'ext5',
      name: '数据库连接器',
      description: '连接各种数据库的工具',
      author: 'DB Connect',
      version: '2.0.0',
      icon: 'database',
      tags: ['数据库', '连接器'],
      installed: true
    },
    {
      id: 'ext6',
      name: '自然语言处理',
      description: '文本分析和处理工具包',
      author: 'NLP Team',
      version: '1.5.2',
      icon: 'document',
      tags: ['NLP', '文本分析'],
      installed: false,
      featured: true
    }
  ];

  async getExtensions(): Promise<ExtensionItem[]> {
    return this.extensions;
  }

  async installExtension(extensionId: string): Promise<boolean> {
    const extension = this.extensions.find(ext => ext.id === extensionId);
    if (extension) {
      extension.installed = true;
      return true;
    }
    return false;
  }

  async uninstallExtension(extensionId: string): Promise<boolean> {
    const extension = this.extensions.find(ext => ext.id === extensionId);
    if (extension) {
      extension.installed = false;
      return true;
    }
    return false;
  }

  async searchExtensions(query: string): Promise<ExtensionItem[]> {
    const lowerQuery = query.toLowerCase();
    return this.extensions.filter(ext => 
      ext.name.toLowerCase().includes(lowerQuery) || 
      ext.description.toLowerCase().includes(lowerQuery) ||
      ext.tags.some((tag: string) => tag.toLowerCase().includes(lowerQuery))
    );
  }

  async disableExtension(extensionId: string): Promise<boolean> {
    return true;
  }

  async enableExtension(extensionId: string): Promise<boolean> {
    return true;
  }
} 