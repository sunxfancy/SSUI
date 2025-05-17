import React, { Component } from 'react';
import { Layout, Model, TabNode, IJsonModel, Actions, DockLocation } from 'flexlayout-react';
import 'flexlayout-react/style/light.css';
import { TreeIcon } from '../WorkSpace/TreeIcon';
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import styles from "./style.module.css";


interface State {
  model: Model;
  activeTabId?: string;
}

export class TabWindowManager extends Component<{}, State> {
  constructor(props: {}) {
    super(props);
    
    // 创建初始布局模型
    const json: IJsonModel = {
      global: {
        tabEnableClose: true,
        tabSetEnableDeleteWhenEmpty: true,
      },
      borders: [],
      layout: {
        type: "row",
        weight: 100,
        children: [
          {
            type: "tabset",
            weight: 100,
            selected: 0,
            children: []
          }
        ]
      }
    };

    this.state = {
      model: Model.fromJson(json)
    };
  }

  // 处理标签页激活
  handleTabActivate = (tabId: string) => {
    this.setState(prevState => ({
      ...prevState,
      activeTabId: tabId
    }));
  };

  // 处理标签页关闭
  handleTabClose = (tabId: string) => {
    this.setState(prevState => {
      const model = prevState.model;
      model.doAction(Actions.deleteTab(tabId));
      return { model };
    });
  };

  // 打开文件
  public openFile(filePath: string, url: string, title?: string) {
    console.log("openFile", filePath, url, title);

    const tabId = filePath;
    const tabTitle = title || this.basename(filePath);

    this.setState(prevState => {
      const model = prevState.model;
      
      // 检查标签是否已存在
      const existingTab = model.getNodeById(tabId);
      if (existingTab) {
        model.doAction(Actions.selectTab(tabId));
        return { model, activeTabId: tabId };
      }

      // 创建新标签
      const tabJson = {
        type: "tab",
        id: tabId,
        name: tabTitle,
        component: "iframe",
        config: { url }
      };

      // 获取当前选中的标签集
      const selectedTabset = model.getActiveTabset();
      if (selectedTabset) {
        model.doAction(Actions.addNode(tabJson, selectedTabset.getId(), DockLocation.CENTER, 0));
      } else {
        // 如果没有选中的标签集，创建新的
        model.doAction(Actions.addNode(tabJson, "root", DockLocation.CENTER, 0));
      }

      return { model, activeTabId: tabId };
    });
  }

  // 打开React组件
  public openReactComponent(component: React.ReactNode, title: string) {
    const tabId = '#internal-' + title;

    this.setState(prevState => {
      const model = prevState.model;
      
      // 检查标签是否已存在
      const existingTab = model.getNodeById(tabId);
      if (existingTab) {
        model.doAction(Actions.selectTab(tabId));
        return { model, activeTabId: tabId };
      }

      // 创建新标签
      const tabJson = {
        type: "tab",
        id: tabId,
        name: title,
        component: "react",
        config: { component }
      };

      // 获取当前选中的标签集
      const selectedTabset = model.getActiveTabset();
      if (selectedTabset) {
        model.doAction(Actions.addNode(tabJson, selectedTabset.getId(), DockLocation.CENTER, 0));
      } else {
        // 如果没有选中的标签集，创建新的
        model.doAction(Actions.addNode(tabJson, "root", DockLocation.CENTER, 0));
      }

      return { model, activeTabId: tabId };
    });
  }

  // 工厂函数，用于创建标签内容
  factory = (node: TabNode) => {
    const component = node.getComponent();
    const config = node.getConfig();

    if (component === "iframe") {
      return <iframe src={config.url} style={{ width: "100%", height: "100%" }} />;
    } else if (component === "react") {
      return config.component;
    }
    return null;
  };

  // 渲染标签标题
  renderTabTitle = (node: TabNode) => {
    return (
      <div className={styles.tabTitle}>
        <span><span className={styles.treeIcon}>{TreeIcon(node.getName())}</span>{node.getName()}</span>
      </div>
    );
  };

  render() {
    return (
      <Layout
        model={this.state.model}
        factory={this.factory}
        onModelChange={(model) => this.setState({ model })}
        onTabSetPlaceHolder={() => {
          return <div className={styles.noTabsContainer}>Open a file to start browsing</div>;
        }}
        onRenderTab={(node, renderValues) => {
          renderValues.content = this.renderTabTitle(node);
        }}
      />
    );
  }

  private basename(path: string): string {
    return path.split(/[/\\]/).reverse()[0];
  }
}

export default TabWindowManager;
