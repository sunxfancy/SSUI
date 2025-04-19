import { Component } from 'react';
import { Tabs, Tab, Card, Elevation } from '@blueprintjs/core';
import CivitaiModels from './components/CivitaiModels';
import LocalModels from './components/LocalModels';
import HuggingfaceModels from './components/HuggingfaceModels';
import { TauriModelsProvider } from './providers/TauriModelsProvider';
import { ModelsProvider } from './providers/IModelsProvider';

interface ModelAddingPageProps {
  // 可以在这里添加需要的属性
}

interface ModelAddingPageState {
  selectedTabId: string;
}


export class ModelAddingPage extends Component<ModelAddingPageProps, ModelAddingPageState> {
  constructor(props: ModelAddingPageProps) {
    super(props);
    this.state = {
      selectedTabId: 'preset'
    };
    // 创建一个模型服务提供者实例
    this.modelsProvider = new TauriModelsProvider();
  }
  modelsProvider: ModelsProvider;

  handleTabChange = (newTabId: string) => {
    this.setState({ selectedTabId: newTabId });
  };

  renderPresetModelsTab() {
    return (
      <Card elevation={Elevation.ZERO}>
        {/* 预设模型组内容将在这里实现 */}
        <div>预设模型组内容</div>
      </Card>
    );
  }

  renderCivitaiTab() {
    return (
      <Card elevation={Elevation.ZERO}>
        <CivitaiModels 
          onModelSelect={(model) => {
            console.log('Selected model:', model);
            // 这里可以添加模型选择后的处理逻辑
          }}
        />
      </Card>
    );
  }

  renderHuggingfaceTab() {
    return (
      <Card elevation={Elevation.ZERO}>
        <HuggingfaceModels 
          onModelSelect={(model) => {
            console.log('选择的Huggingface模型:', model);
            // 这里可以添加模型选择后的处理逻辑
          }}
        />
      </Card>
    );
  }

  renderLocalModelsTab() {
    return (
      <Card elevation={Elevation.ZERO}>
        <LocalModels
          modelsProvider={this.modelsProvider}
          onModelAdd={(modelPath) => {
            console.log('添加模型:', modelPath);
            // 这里添加模型添加后的处理逻辑
          }}
        />
      </Card>
    );
  }

  render() {
    return (
      <div style={{ padding: ' 0px 20px 0px 20px ', height: '100%', overflow: 'auto' }}>
        <Tabs
          id="ModelAddingTabs"
          selectedTabId={this.state.selectedTabId}
          onChange={this.handleTabChange}
          renderActiveTabPanelOnly={true}
        >
          <Tab 
            id="preset" 
            title="预设模型组" 
            panel={this.renderPresetModelsTab()} 
          />
          <Tab 
            id="civitai" 
            title="Civitai" 
            panel={this.renderCivitaiTab()} 
          />
          <Tab 
            id="huggingface" 
            title="Huggingface" 
            panel={this.renderHuggingfaceTab()} 
          />
          <Tab 
            id="local" 
            title="本地模型" 
            panel={this.renderLocalModelsTab()} 
          />
        </Tabs>
      </div>
    );
  }
}

export default ModelAddingPage;
