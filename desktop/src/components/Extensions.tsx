import React, { Component } from 'react';
import { 
  Button, 
  InputGroup, 
  Tabs, 
  Tab, 
  Card, 
  Elevation, 
  Tag, 
  Icon
} from '@blueprintjs/core';
import { IconName } from '@blueprintjs/icons';

interface ExtensionItem {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  icon: IconName;
  tags: string[];
  installed?: boolean;
  featured?: boolean;
}

interface ExtensionsProps {
  onOpenExtensionStore?: () => void;
}


interface ExtensionsState {
  searchQuery: string;
  isSearching: boolean;
  extensions: ExtensionItem[];
}

export class Extensions extends Component<ExtensionsProps, ExtensionsState> {
  constructor(props: ExtensionsProps) {
    super(props);
    this.state = {
      searchQuery: '',
      isSearching: false,
      extensions: [
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
      ]
    };
  }

  handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const query = event.target.value;
    this.setState({
      searchQuery: query,
      isSearching: query.length > 0
    });
  };

  clearSearch = () => {
    this.setState({
      searchQuery: '',
      isSearching: false
    });
  };

  openExtensionStore = () => {
    // 打开扩展商城的逻辑
    this.props.onOpenExtensionStore?.();
  };

  installExtension = (extensionId: string) => {
    this.setState(prevState => ({
      extensions: prevState.extensions.map(ext => 
        ext.id === extensionId ? { ...ext, installed: true } : ext
      )
    }));
  };

  uninstallExtension = (extensionId: string) => {
    this.setState(prevState => ({
      extensions: prevState.extensions.map(ext => 
        ext.id === extensionId ? { ...ext, installed: false } : ext
      )
    }));
  };

  renderExtensionCard = (extension: ExtensionItem) => {
    return (
      <Card 
        key={extension.id} 
        elevation={Elevation.ONE}
        style={{ 
          margin: '10px 0', 
          display: 'flex', 
          flexDirection: 'column'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start' }}>
          <div style={{ 
            width: '48px', 
            height: '48px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            backgroundColor: '#f0f0f0', 
            borderRadius: '4px',
            marginRight: '12px'
          }}>
            <Icon icon={extension.icon} size={24} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: '0 0 5px 0' }}>{extension.name}</h3>
              {extension.installed ? (
                <Button 
                  small 
                  intent="danger" 
                  onClick={() => this.uninstallExtension(extension.id)}
                >
                  卸载
                </Button>
              ) : (
                <Button 
                  small 
                  intent="success" 
                  onClick={() => this.installExtension(extension.id)}
                >
                  安装
                </Button>
              )}
            </div>
            <p style={{ margin: '0 0 8px 0', color: '#666' }}>{extension.description}</p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                {extension.tags.map(tag => (
                  <Tag key={tag} minimal style={{ marginRight: '5px' }}>{tag}</Tag>
                ))}
              </div>
              <div style={{ fontSize: '12px', color: '#888' }}>
                {extension.author} | v{extension.version}
              </div>
            </div>
          </div>
        </div>
      </Card>
    );
  };

  render() {
    const { searchQuery, isSearching, extensions } = this.state;
    
    const installedExtensions = extensions.filter(ext => ext.installed);
    const featuredExtensions = extensions.filter(ext => ext.featured);
    const searchResults = extensions.filter(ext => 
      ext.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
      ext.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ext.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    return (
      <div style={{ padding: '15px', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', marginBottom: '15px' }}>
            <div style={{ flex: 1, marginRight: '10px' }}>
          <InputGroup
            leftIcon="search"
            placeholder="搜索扩展..."
            value={searchQuery}
            onChange={this.handleSearchChange}
            rightElement={
              isSearching ? 
                <Button icon="cross" minimal onClick={this.clearSearch} /> : 
                undefined
            }
          />
          </div>
          <Button 
            icon="shop" 
            intent="primary"
            onClick={this.openExtensionStore}
          >
            扩展商城
          </Button>
        </div>

        {isSearching ? (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <h3>搜索结果</h3>
            {searchResults.length > 0 ? (
              searchResults.map(this.renderExtensionCard)
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
                未找到匹配的扩展
              </div>
            )}
          </div>
        ) : (
          <Tabs id="extensions-tabs">
            <Tab 
              id="installed" 
              title="已安装" 
              panel={
                <div style={{ overflowY: 'auto', padding: '10px 0' }}>
                  {installedExtensions.length > 0 ? (
                    installedExtensions.map(this.renderExtensionCard)
                  ) : (
                    <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
                      暂无已安装的扩展
                    </div>
                  )}
                </div>
              } 
            />
            <Tab 
              id="featured" 
              title="精选扩展" 
              panel={
                <div style={{ overflowY: 'auto', padding: '10px 0' }}>
                  {featuredExtensions.map(this.renderExtensionCard)}
                </div>
              } 
            />
            <Tabs.Expander />
          </Tabs>
        )}
      </div>
    );
  }
}

export default Extensions;
