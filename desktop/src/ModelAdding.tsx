import { Component } from 'react';
import { Tabs, Tab, Card, Elevation } from '@blueprintjs/core';
import CivitaiModels from './components/CivitaiModels';

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
  }

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
        {/* Huggingface模型内容将在这里实现 */}
        <div>Huggingface模型内容</div>
      </Card>
    );
  }

  renderLocalModelsTab() {
    return (
      <Card elevation={Elevation.ZERO}>
        {/* 本地模型内容将在这里实现 */}
        <div>本地模型内容</div>
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
