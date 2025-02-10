import React, { Component } from 'react';
import { Tabs, Tab, TabId } from "@blueprintjs/core";
import { Allotment } from "allotment";

interface TabData {
  id: string;
  title: string;
  content: JSX.Element;
  parent?: PaneNode;
}

interface PaneNode {
  id: string;
  tabs?: TabData[];
  vertical?: boolean;
  children?: PaneNode[];
}

interface State {
  rootPane: PaneNode;
  selectedTab?: TabData;
}

class TabWindowManager extends Component<{}, State> {
  state: State = {
    rootPane: this.linkTabAndPane({
      id: "root",
      vertical: true,
      children: [
        {
          id: "pane1",
          tabs: [
            { id: "tab1", title: "Tab 1", content: <div>Content of Tab 1</div> },
            { id: "tab2", title: "Tab 2", content: <div>Content of Tab 2</div> }
          ]
        },
        {
          id: "additionalPane",
          tabs: [
            { id: "tab3", title: "Tab 3", content: <div>Content of Tab 3</div> }
          ]
        }
      ]
    })
  };

  linkTabAndPane(pane: PaneNode) {
    if (pane.tabs) {
      pane.tabs.forEach(tab => {
        tab.parent = pane;
      });
    }
    if (pane.children) {
      pane.children.forEach(child => this.linkTabAndPane(child)); 
    }
    return pane;
  }

  handleTabChange = (newTabId: string | number) => {
    const findTab = (pane: PaneNode, tabId: string): TabData | undefined => {
      if (pane.tabs) {
        const tab = pane.tabs.find(tab => tab.id === tabId);
        if (tab) return tab;
      }
      if (pane.children) {
        for (const child of pane.children) {
          const result = findTab(child, tabId);
          if (result) return result;
        }
      }
    }

    this.setState({
      selectedTab: findTab(this.state.rootPane, newTabId.toString())
    });
  };

  handleTabDragEnd = (tab: TabData, targetPaneId: string, position: 'left' | 'right' | 'top' | 'bottom') => {
    this.setState(prevState => {
      const newRootPane = this.updatePaneStructure(prevState.rootPane, tab.id, targetPaneId, position);
      return { rootPane: newRootPane };
    });
  };

  updatePaneStructure = (pane: PaneNode, tabId: string, targetPaneId: string, position: 'left' | 'right' | 'top' | 'bottom'): PaneNode => {
    if (pane.id === targetPaneId) {
      const newTab = { id: tabId, title: `New Tab ${tabId}`, content: <div>Content of {tabId}</div> };
      if (position === 'left' || position === 'right') {
        const newPane: PaneNode = { id: `newPane-${tabId}`, tabs: [newTab] };
        return {
          ...pane,
          tabs: undefined,
          children: position === 'left' ? [newPane, pane] : [pane, newPane]
        };
      } else {
        const newPane: PaneNode = { id: `newPane-${tabId}`, tabs: [newTab] };
        return {
          ...pane,
          tabs: undefined,
          children: position === 'top' ? [newPane, pane] : [pane, newPane]
        };
      }
    }

    if (pane.children) {
      return {
        ...pane,
        children: pane.children.map(child => this.updatePaneStructure(child, tabId, targetPaneId, position))
      };
    }

    return pane;
  };

  openFile = (filePath: string) => {
    console.log("openFile", filePath);
    let currentPane = this.state.selectedTab?.parent;
    let newTab = {
      id: filePath,
      title: "Opened File",
      content: <iframe src={"http://localhost:7420/?path=" + filePath} style={{ width: "100%", height: "100%" }} />
    } as TabData;


    if (!currentPane) {
      this.setState({
        rootPane: this.linkTabAndPane({
          id: "root",
          tabs: [newTab]
        }),
        selectedTab: newTab
      });
    }

  }

  renderPane = (pane: PaneNode) => {
    return (pane.tabs && pane.tabs.length > 0) ?
          <Tabs
            id={`Tabs-${pane.id}`}
            className='tabs-container'
            onChange={(newTabId: TabId) => this.handleTabChange(newTabId)}
            selectedTabId={this.state.selectedTab?.id}
          >
            {pane.tabs.map(tab => (
              <Tab
                key={tab.id}
                id={tab.id}
                title={tab.title}
                panel={tab.content}
                draggable
                onDragEnd={(e) => {
                  const position = this.determineDropPosition(e); // Implement this function to determine the drop position
                  this.handleTabDragEnd(tab, pane.id, position);
                }}
              />
            ))}
            {/* 可以根据需要动态添加更多标签 */}
          </Tabs>
        :
      <Allotment key={pane.id} vertical={pane.vertical}>
        {pane.children && pane.children.map(childPane => this.renderPane(childPane))}
      </Allotment>;
  };

  determineDropPosition = (e: React.DragEvent): 'left' | 'right' | 'top' | 'bottom' => {
    // Implement logic to determine the drop position based on the event
    // For example, you can use the mouse position relative to the pane

    return 'right'; // Placeholder return value
  };

  render() {
    return this.renderPane(this.state.rootPane);
  }
}

export default TabWindowManager;