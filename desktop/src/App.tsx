import React, { Component } from 'react';
import { load } from '@tauri-apps/plugin-store';
import Sidebar from './components/Sidebar.tsx';
import TabWindowManager from './components/TabWindowManager';
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { Topbar } from './components/Topbar';
import { ModelManager } from './components/Model';
import ModelAddingPage from './ModelAdding.tsx';
import Queue from './components/Queue.tsx';
import { open } from '@tauri-apps/plugin-dialog';
import NewWorkflow from './components/NewWorkflow.tsx';
import { Extensions } from './components/Extensions.tsx';
import { ModelManagerProvider } from './providers/ModelManagerProvider';

class App extends Component {
  tabWindowManagerRef = React.createRef<TabWindowManager>();
  state = {
    currentWorkspace: null,
    isNewWorkflowDialogOpen: false,
  };

  // 创建一个模型管理提供者实例
  private modelManagerProvider = new ModelManagerProvider();

  async onClick() {
    const store = await load('settings.json', { autoSave: false });
    await store.set('root', undefined);
    await store.save();
  }

  onOpenWorkspace = () => {
    const options = {
      directory: true,
      multiple: false
    };
    open(options).then(async (result: string | null) => {
      if (result) {
        this.setState({ currentWorkspace: result });
      }
    });
  }

  onSelectWorkflow = () => {
    this.setState({ isNewWorkflowDialogOpen: true });
  }

  onFileOpen = (filePath: string) => {
    this.tabWindowManagerRef.current?.openFile(filePath, "http://localhost:7420/?path=" + filePath);
  }

  addModel = () => {
    this.tabWindowManagerRef.current?.openReactComponent(<ModelAddingPage />, "添加模型");
  }

  openExtensionStore = () => {
    this.tabWindowManagerRef.current?.openFile("#internal-extension-store", "https://sunxfancy.github.io/test_page/", "扩展商城");
  }

  handleWorkflowSelect = (workflowIds: string[], targetPath: string) => {
    // TODO：将workflowIds转换为文件然后写入到目标文件夹中
    console.log(workflowIds);
    this.setState({ isNewWorkflowDialogOpen: false, currentWorkspace: targetPath });
  }

  render() {
    return (
      <div style={{ height: '100%' }}>
        <Allotment>
          <Allotment.Pane minSize={100} maxSize={500}>
            <Topbar>
              <Sidebar currentWorkspace={this.state.currentWorkspace} onOpenWorkspace={this.onOpenWorkspace} onSelectWorkflow={this.onSelectWorkflow} onFileOpen={this.onFileOpen} />
              <ModelManager provider={this.modelManagerProvider} addModel={this.addModel} />
              <Queue />
              <Extensions onOpenExtensionStore={this.openExtensionStore} />
            </Topbar>
          </Allotment.Pane>
          <Allotment.Pane>
            <TabWindowManager ref={this.tabWindowManagerRef} />
          </Allotment.Pane>
        </Allotment>
        <NewWorkflow isOpen={this.state.isNewWorkflowDialogOpen} onClose={() => this.setState({ isNewWorkflowDialogOpen: false })} onWorkflowSelect={this.handleWorkflowSelect} />
      </div>
    );
  }
}

export default App;
