import React, { Component } from 'react';
import { Tabs, Tab } from "@blueprintjs/core";
import { Allotment } from "allotment";

interface TabData {
  id: string;
  title: string;
  content: JSX.Element;
}

interface PaneNode {
  id: string;
  tabs?: TabData[];
  vertical?: boolean;
  children?: PaneNode[];
}

interface State {
  rootPane: PaneNode;
  selectedTabId: { [key: string]: string };
}

class TabWindowManager extends Component<{}, State> {
  state: State = {
    rootPane: {
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
    },
    selectedTabId: { pane1: "tab1" }
  };

  handleTabChange = (paneId: string, newTabId: string | number) => {
    this.setState(prevState => ({
      selectedTabId: { ...prevState.selectedTabId, [paneId]: newTabId.toString() }
    }));
  };

  handleTabDragEnd = (tabId: string, targetPaneId: string, position: 'left' | 'right' | 'top' | 'bottom') => {
    this.setState(prevState => {
      const newRootPane = this.updatePaneStructure(prevState.rootPane, tabId, targetPaneId, position);
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
          children: position === 'left' ? [newPane, pane] : [pane, newPane]
        };
      } else {
        const newPane: PaneNode = { id: `newPane-${tabId}`, tabs: [newTab] };
        return {
          ...pane,
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
    
  }

  renderPane = (pane: PaneNode) => {
    return (
      <Allotment key={pane.id} vertical={pane.vertical}>
        {pane.tabs && pane.tabs.length > 0 && (
        <div>
          <Tabs
            id={`Tabs-${pane.id}`}
            onChange={(newTabId: string | number) => this.handleTabChange(pane.id, newTabId)}
            selectedTabId={this.state.selectedTabId[pane.id]}
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
                  this.handleTabDragEnd(tab.id, pane.id, position);
                }}
              />
            ))}
            {/* 可以根据需要动态添加更多标签 */}
          </Tabs>
          </div>
        )}
        {pane.children && pane.children.map(childPane => this.renderPane(childPane))}
      </Allotment>

    );
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