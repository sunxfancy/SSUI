import React, { Component } from 'react';
import { load } from '@tauri-apps/plugin-store';
import Sidebar from './components/Sidebar.tsx';
import TabWindowManager from './components/TabWindowManager';
import { Allotment } from "allotment";
import "allotment/dist/style.css";

class App extends Component {
  tabWindowManagerRef = React.createRef<TabWindowManager>();
  state = {
    currentWorkspace: null,
  };


  async onClick() {
    const store = await load('settings.json', { autoSave: false });
    await store.set('root', undefined);
    await store.save();
  }

  onOpenWorkspace = (workspace: string) => {
    this.setState({ currentWorkspace: workspace });
  }

  onFileOpen = (filePath: string) => {
    this.tabWindowManagerRef.current?.openFile(filePath, "http://localhost:7420/?path=" + filePath);
  }

  render() {
    return (
      <Allotment>
        <Allotment.Pane minSize={100} maxSize={500}>
          <Sidebar currentWorkspace={this.state.currentWorkspace} onOpenWorkspace={this.onOpenWorkspace} onFileOpen={this.onFileOpen} />
        </Allotment.Pane>
        <Allotment.Pane>
          <TabWindowManager ref={this.tabWindowManagerRef} />
        </Allotment.Pane>
      </Allotment>
    );
  }
}

export default App;
