import React, { Component } from 'react';
import { Tabs, Tab, TabId, Button } from "@blueprintjs/core";
import { Allotment } from "allotment";
import "allotment/dist/style.css";

import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "./TabWindowManager.css";
import { produce } from 'immer';


interface TabData {
  id: string;
  title: string;
  content: JSX.Element;
  parent: TabsNode;
}

interface PaneNode {
  id: string;
  parent?: ContainerNode;
  isTabs(): boolean;
  isEmpty(): boolean;
  find(predicate: (tab: TabData) => boolean): TabData | undefined;
  findPane(predicate: (pane: PaneNode) => boolean): PaneNode | undefined;
}

class TabsNode implements PaneNode {
  id: string;
  tabs: TabData[];
  selected?: TabData;
  parent?: ContainerNode;

  constructor(id: string, tabs: TabData[] = [], selected?: TabData) {
    this.id = id;
    this.tabs = tabs;
    this.selected = selected;
  }

  isTabs(): boolean {
    return true;
  }
  isEmpty(): boolean {
    return this.tabs.length === 0;
  }

  find(predicate: (tab: TabData) => boolean): TabData | undefined {
    return this.tabs.find(predicate);
  }

  findPane(predicate: (pane: PaneNode) => boolean): PaneNode | undefined {
    if (predicate(this)) {
      return this;
    }
    return undefined;
  }
}

class ContainerNode implements PaneNode {
  id: string;
  children: PaneNode[];
  vertical: boolean;
  parent?: ContainerNode;

  constructor(id: string, children: PaneNode[] = [], vertical: boolean = false) {
    this.id = id;
    this.children = children;
    this.vertical = vertical;
  }

  isTabs(): boolean {
    return false;
  }
  isEmpty(): boolean {
    return this.children.length === 0;
  }

  find(predicate: (tab: TabData) => boolean): TabData | undefined {
    for (const child of this.children) {
      const result = child.find(predicate);
      if (result) return result;
    }
    return undefined;
  }

  findPane(predicate: (pane: PaneNode) => boolean): PaneNode | undefined {
    if (predicate(this)) {
      return this;
    }
    for (const child of this.children) {
      const result = child.findPane(predicate);
      if (result) return result;
    }
    return undefined;
  }
}

interface State {
  rootPane: PaneNode;
  selectedTab?: TabData;
  visualRect?: { left: number, top: number, width: number, height: number };
}

type DropPosition = 'left' | 'right' | 'top' | 'bottom' | 'center';

export class TabWindowManager extends Component<{}, State> {
  state: State = {
    rootPane: new TabsNode("root")
  };

  handleTabActivate = (newTabId: string | number) => {
    console.log("handleTabActivate", newTabId);
    this.setState(prevState => produce(prevState, draft => {
      let find_tab = draft.rootPane.find(t => t.id === newTabId.toString());
      if (find_tab && find_tab.id != draft.selectedTab?.id) {
        draft.selectedTab = find_tab;
      }
      if (draft.selectedTab?.parent) {
        if (draft.selectedTab.parent.selected?.id != draft.selectedTab.id) {
          draft.selectedTab.parent.selected = draft.selectedTab;
        }
      }
    }));
  };

  handleTabDragEnd = (tab: TabData, targetPaneId: string, position: DropPosition) => {
    console.log("handleTabDragEnd", tab.id, targetPaneId, position);
    this.setState({ visualRect: undefined });

    this.setState(prevState => produce(prevState, draft => {
      // 找到拖动的标签和目标面板
      let draftTab = draft.rootPane.find((t: TabData) => t.id === tab.id);
      let targetPane = draft.rootPane.findPane(p => p.id === targetPaneId);

      if (!draftTab || !targetPane) return;

      let draftTab_copy = {
        id: draftTab.id,
        title: draftTab.title,
        content: draftTab.content,
        parent: draftTab.parent
      };

      // 从原面板移除标签
      this.removeTab(draftTab, draft);

      if (position === 'center') {
        // 如果目标是标签面板，直接添加到此面板
        if (targetPane.isTabs()) {
          const tabsPane = targetPane as TabsNode;
          draftTab_copy.parent = tabsPane;
          tabsPane.tabs.push(draftTab_copy);
          tabsPane.selected = draftTab_copy;
        }
      } else {
        // 创建新的标签面板
        let newTabsNode = new TabsNode(`tabs-${Date.now()}`, [draftTab_copy]);
        draftTab_copy.parent = newTabsNode;
        newTabsNode.selected = draftTab_copy;

        // 根据位置确定是垂直还是水平分割
        const isVertical = position === 'top' || position === 'bottom';

        if (targetPane.parent) {
          // 目标已经在容器中
          let parent = targetPane.parent;

          // 如果父容器方向与当前拖放方向一致，直接添加到父容器
          if ((parent.vertical && isVertical) || (!parent.vertical && !isVertical)) {
            const insertIndex = parent.children.findIndex(c => c.id === targetPane.id);
            const newIndex = position === 'bottom' || position === 'right' ? insertIndex + 1 : insertIndex;
            parent.children.splice(newIndex, 0, newTabsNode);
            newTabsNode.parent = parent;
          } else {
            // 创建新的容器节点替换目标在父容器中的位置
            let newContainer = new ContainerNode(`container-${Date.now()}`, [], isVertical);
            newContainer.parent = parent;

            // 在父容器中替换目标节点
            for (let i = 0; i < parent.children.length; i++) {
              if (parent.children[i].id === targetPane.id) {
                parent.children[i] = newContainer;
                break;
              }
            }

            // 根据拖放位置决定子节点顺序
            if (position === 'top' || position === 'left') {
              newContainer.children = [newTabsNode, targetPane];
            } else {
              newContainer.children = [targetPane, newTabsNode];
            }

            newTabsNode.parent = newContainer;
            targetPane.parent = newContainer;
          }
        } else {
          // 目标是根节点，创建新的容器作为根节点
          let newContainer = new ContainerNode("root-container", [], isVertical);

          // 根据拖放位置决定子节点顺序
          if (position === 'top' || position === 'left') {
            newContainer.children = [newTabsNode, targetPane];
          } else {
            newContainer.children = [targetPane, newTabsNode];
          }

          newTabsNode.parent = newContainer;
          targetPane.parent = newContainer;

          // 更新根节点
          draft.rootPane = newContainer;
        }
      }

      // 更新选中的标签
      draft.selectedTab = draftTab_copy;
    }));
  };

  public removeTab(tab: TabData, state: State) {
    let tabsNode = tab.parent;
    if (tabsNode) {
      let onlyOneTabLeft = tabsNode.tabs.length === 1;

      // 如果选中的标签被删除，则选中后一个，如没有则选中前一个
      if (tabsNode.selected?.id === tab.id && !onlyOneTabLeft) {
        let index = tabsNode.tabs.findIndex(t => t.id === tab.id);
        if (index < tabsNode.tabs.length - 1) {
          tabsNode.selected = tabsNode.tabs[index + 1];
        } else if (index > 0) {
          tabsNode.selected = tabsNode.tabs[index - 1];
        } 
      }

      tabsNode.tabs = tabsNode.tabs.filter(t => t.id !== tab.id);
      if (onlyOneTabLeft && tabsNode.parent) {
        this.removePane(tabsNode);
      } 

      // 如果全局最近选中的标签被删除，则选中刚刚选中的标签
      if (state.selectedTab?.id === tab.id) {
        if (!onlyOneTabLeft) {
          state.selectedTab = tabsNode.selected;
        } else {
          let root = state.rootPane;
          while (root instanceof ContainerNode) {
            root = root.children[0];
          }
          if (root instanceof TabsNode) {
            state.selectedTab = root.selected;
          }
        }
      }
    }
  }

  public removePane(pane: PaneNode) {
    let parent = pane.parent;
    let removed_id = pane.id;
    if (parent) {
      parent.children = parent.children.filter(child => child.id !== removed_id);
      if (parent.children.length === 1) {
        let grandParent = parent.parent;
        if (grandParent) {
          // 将parent的第一个子节点移动到grandParent的children中
          for (let i = 0; i < grandParent.children.length; i++) {
            if (grandParent.children[i].id === parent.id) {
              grandParent.children[i] = parent.children[0];
              parent.children[0].parent = grandParent;
              break;
            }
          }
        }
      }
    }
  }

  public async openFile(filePath: string, url: string, title?: string) {
    console.log("openFile", filePath);

    this.setState(produce(this.state, draft => {
      // Find if the file is already open
      let find_tab = draft.rootPane.find(t => t.id === filePath);
      if (find_tab) {
        this.handleTabActivate(find_tab.id);
        return;
      }
      let currentPane = draft.selectedTab?.parent ?? draft.rootPane as TabsNode;

      let newTab = {
        id: filePath,
        title: title || basename(filePath),
        content: <iframe src={url} style={{ width: "100%", height: "100%" }} />,
        parent: currentPane
      } as TabData;

      let draft_panel = draft.rootPane.findPane(p => p.id === currentPane.id);
      if (draft_panel) {
        let tab_panel = (draft_panel as TabsNode);
        tab_panel.tabs.push(newTab);
        tab_panel.selected = newTab;
      }
      draft.selectedTab = newTab;
    }));
  }

  handleTabClose = (tab: TabData): void => {
    this.setState(prevState => produce(prevState, draft => {
      let draft_tab = draft.rootPane.find(t => t.id === tab.id);
      if (draft_tab) { this.removeTab(draft_tab, draft); }
    }));
  }

  draggingTab?: TabData;

  renderTabs(tabs: TabsNode, pane: PaneNode) {
    if (tabs.isEmpty()) {
      return [<NoTabs key="no-tabs" />];
    }
    return tabs.tabs.map(tab => (<Tab
      key={tab.id}
      id={tab.id}
      title={<TabTitle title={tab.title} onClose={() => this.handleTabClose(tab)} />}
      panel={tab.content}
      onClickCapture={(e) => {
        this.handleTabActivate(tab.id);
      }}

      draggable
      onDragStart={(e) => {
        console.log("onDragStart", tab.id);
        this.draggingTab = tab;
      }}
      onDragOver={(e) => {
        const target = e.currentTarget as HTMLElement;
        const rect = target.getBoundingClientRect();
        let visualRect = {
          left: rect.left,
          top: rect.top,
          width: rect.width,
          height: rect.height
        }
        this.setState({
          visualRect: visualRect
        });
      }}
      onDragEnd={(e) => {
        if (this.draggingTab) {
          const position = this.determineDropPosition(e);
          this.handleTabDragEnd(this.draggingTab, pane.id, position);
        }
      }}
    />));
  }

  renderPane(pane: PaneNode) {
    if (pane.isTabs()) {
      return <Tabs
        id={`Tabs-${pane.id}`}
        className='tabs-container'
        onChange={(newTabId: TabId, prevTabId?: TabId) => {
          if (newTabId != prevTabId) {this.handleTabActivate(newTabId)}
        }}
        selectedTabId={(pane as TabsNode).selected?.id}
      >
        {this.renderTabs(pane as TabsNode, pane)}
      </Tabs>
    } else {
      return <Allotment className='allotment-container' key={pane.id} vertical={(pane as ContainerNode).vertical} minSize={150}>
        {(pane as ContainerNode).children && (pane as ContainerNode).children.map(childPane => this.renderPane(childPane))}
      </Allotment>;
    }
  };

  determineDropPosition = (e: React.DragEvent): DropPosition => {
    const target = e.target as HTMLElement;
    const rect = target.getBoundingClientRect();
    const mouse = { x: e.clientX, y: e.clientY };
    const centerRect = {
      left: rect.left + (rect.width * 0.1),
      top: rect.top + (rect.height * 0.1),
      width: rect.width * 0.8,
      height: rect.height * 0.8
    }

    if (mouse.x > centerRect.left && mouse.x < centerRect.left + centerRect.width && mouse.y > centerRect.top && mouse.y < centerRect.top + centerRect.height) {
      return 'center';
    }

    if (mouse.x > centerRect.left && mouse.x < centerRect.left + centerRect.width) {
      return mouse.y > centerRect.top ? 'bottom' : 'top';
    }

    if (mouse.y > centerRect.top && mouse.y < centerRect.top + centerRect.height) {
      return mouse.x > centerRect.left ? 'right' : 'left';
    }

    return 'center';
  };

  render() {
    return (
      <>
        {this.state.visualRect && (
          <div
            style={{
              position: 'fixed',
              left: this.state.visualRect.left + 'px',
              top: this.state.visualRect.top + 'px',
              width: this.state.visualRect.width + 'px',
              height: this.state.visualRect.height + 'px',
              backgroundColor: 'rgba(0, 120, 255, 0.2)',
              border: '2px dashed rgba(0, 120, 255, 0.8)',
              pointerEvents: 'none',
              zIndex: 9999
            }}
          />
        )}
        {this.renderPane(this.state.rootPane)}
      </>
    );
  }
}

class TabTitle extends React.Component<{ title: string, onClose: () => void }> {
  state = {
    isHovered: false
  };

  handleMouseEnter = () => {
    this.setState({ isHovered: true });
  };

  handleMouseLeave = () => {
    this.setState({ isHovered: false });
  };

  render() {
    return (
      <span
        onMouseEnter={this.handleMouseEnter}
        onMouseLeave={this.handleMouseLeave}
      >
        {this.props.title}
        <Button
          icon="cross"
          variant='minimal'
          onClick={this.props.onClose}
          style={{
            visibility: this.state.isHovered ? 'visible' : 'hidden',
            opacity: this.state.isHovered ? 1 : 0,
            transition: 'opacity 0.2s ease-in-out'
          }}
        />
      </span>
    );
  }
}


class NoTabs extends React.Component {
  render() {
    return <div className='no-tabs-container'>Open a file to start browsing</div>;
  }
}

function basename(path: string) { return path.split(/[/\\]/).reverse()[0]; }

export default TabWindowManager;