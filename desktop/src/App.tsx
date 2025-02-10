import React, { Component } from 'react';
import { Button } from "@blueprintjs/core";
import { load } from '@tauri-apps/plugin-store';
import Sidebar from './components/Sidebar.tsx';
import TabWindowManager from './components/TabWindowManager';
import { Allotment } from "allotment";
import "allotment/dist/style.css";

class App extends Component {
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

  render() {
    return (
      <Allotment>
        <Allotment.Pane minSize={100} maxSize={500}>
          <Sidebar currentWorkspace={this.state.currentWorkspace} onOpenWorkspace={this.onOpenWorkspace} />

        </Allotment.Pane>
        <Allotment.Pane>
          <TabWindowManager />
        </Allotment.Pane>
      </Allotment>
    );
  }
}

export default App;
