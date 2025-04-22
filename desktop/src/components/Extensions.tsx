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
import { ExtensionsProvider } from '../providers/ExtensionsProvider';
import { IExtensionsProvider } from '../providers/IExtensionsProvider';

export interface ExtensionItem {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  icon: IconName;
  tags: string[];
  installed?: boolean;
  featured?: boolean;
  disabled?: boolean;
}

interface ExtensionsProps {
  provider?: IExtensionsProvider;
  onOpenExtensionStore?: () => void;
}


interface ExtensionsState {
  searchQuery: string;
  isSearching: boolean;
  extensions: ExtensionItem[];
}

export class Extensions extends Component<ExtensionsProps, ExtensionsState> {
  private provider: IExtensionsProvider;

  constructor(props: ExtensionsProps) {
    super(props);
    this.provider = props.provider || new ExtensionsProvider();
    this.state = {
      searchQuery: '',
      isSearching: false,
      extensions: []
    };
  }

  async componentDidMount() {
    try {
      const extensions = await this.provider.getExtensions();
      this.setState({ extensions });
    } catch (error) {
      console.error("加载扩展数据失败:", error);
    }
  }

  handleSearchChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const query = event.target.value;
    this.setState({
      searchQuery: query,
      isSearching: query.length > 0
    });

    if (query.length > 0) {
      try {
        const searchResults = await this.provider.searchExtensions(query);
        this.setState({ extensions: searchResults });
      } catch (error) {
        console.error("搜索扩展失败:", error);
      }
    } else {
      try {
        const allExtensions = await this.provider.getExtensions();
        this.setState({ extensions: allExtensions });
      } catch (error) {
        console.error("加载扩展数据失败:", error);
      }
    }
  };

  clearSearch = async () => {
    this.setState({
      searchQuery: '',
      isSearching: false
    });
    try {
      const extensions = await this.provider.getExtensions();
      this.setState({ extensions });
    } catch (error) {
      console.error("加载扩展数据失败:", error);
    }
  };

  openExtensionStore = () => {
    this.props.onOpenExtensionStore?.();
  };

  installExtension = async (extensionId: string) => {
    try {
      const success = await this.provider.installExtension(extensionId);
      if (success) {
        const extensions = await this.provider.getExtensions();
        this.setState({ extensions });
      }
    } catch (error) {
      console.error("安装扩展失败:", error);
    }
  };

  uninstallExtension = async (extensionId: string) => {
    try {
      const success = await this.provider.uninstallExtension(extensionId);
      if (success) {
        const extensions = await this.provider.getExtensions();
        this.setState({ extensions });
      }
    } catch (error) {
      console.error("卸载扩展失败:", error);
    }
  };

  disableExtension = async (extensionId: string) => {
    try {
      const success = await this.provider.disableExtension(extensionId);
      if (success) {
        const extensions = await this.provider.getExtensions();
        this.setState({ extensions });
      }
    } catch (error) {
      console.error("禁用扩展失败:", error);
    }
  };

  enableExtension = async (extensionId: string) => {
    try {
      const success = await this.provider.enableExtension(extensionId);
      if (success) {
        const extensions = await this.provider.getExtensions();
        this.setState({ extensions });
      }
    } catch (error) {
      console.error("启用扩展失败:", error);
    }
  };

  renderExtensionCard = (extension: ExtensionItem) => {
    const isProduction = import.meta.env.PROD;
    
    return (
      <Card 
        key={extension.id} 
        elevation={Elevation.ONE}
        style={{ 
          margin: '10px 5px', 
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
              <div style={{ display: 'flex', gap: '8px' }}>
                {extension.installed && (
                  <>
                    {extension.disabled ? (
                      <Button 
                        small 
                        intent="warning" 
                        onClick={() => this.enableExtension(extension.id)}
                      >
                        启用
                      </Button>
                    ) : (
                      <Button 
                        small 
                        intent="warning" 
                        onClick={() => this.disableExtension(extension.id)}
                      >
                        禁用
                      </Button>
                    )}
                    {isProduction && (
                      <Button 
                        small 
                        intent="danger" 
                        onClick={() => this.uninstallExtension(extension.id)}
                      >
                        卸载
                      </Button>
                    )}
                  </>
                )}
                {!extension.installed && (
                  <Button 
                    small 
                    intent="success" 
                    onClick={() => this.installExtension(extension.id)}
                  >
                    安装
                  </Button>
                )}
              </div>
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
            {extensions.length > 0 ? (
              extensions.map(this.renderExtensionCard)
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
                未找到匹配的扩展
              </div>
            )}
          </div>
        ) : (
          <div style={{ height: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column' }}>
            <Tabs id="extensions-tabs">
              <Tab 
                id="installed" 
                title="已安装" 
                panel={
                  <div style={{ overflowY: 'auto', padding: '10px 0', height: 'calc(100vh - 150px)' }}>
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
                  <div style={{ overflowY: 'auto', padding: '10px 0', height: 'calc(100vh - 150px)' }}>
                    {featuredExtensions.map(this.renderExtensionCard)}
                  </div>
                } 
              />
              <Tabs.Expander />
            </Tabs>
          </div>
        )}
      </div>
    );
  }
}

export default Extensions;
