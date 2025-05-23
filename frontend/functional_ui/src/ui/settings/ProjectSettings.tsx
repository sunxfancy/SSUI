import React, { Component } from 'react';
import { ConfigItem, ConfigGroup } from './types';
import { mockConfigData } from './mockData';
import './ProjectSettings.css';
import { registerUIProvider, UIProvider } from '../UIProvider';

// 布尔类型配置项组件
class BooleanConfig extends Component<{ item: ConfigItem; onChange: (value: boolean) => void }> {
  render() {
    const { item, onChange } = this.props;
    return (
      <div className="config-item">
        <div className="config-header">
          <label className="config-label">{item.name}</label>
          <div className="config-tooltip" title={item.description}>?</div>
        </div>
        <div className="config-control">
          <input
            type="checkbox"
            checked={item.value}
            onChange={(e) => onChange(e.target.checked)}
          />
        </div>
      </div>
    );
  }
}

// 枚举类型配置项组件
class EnumConfig extends Component<{ item: ConfigItem; onChange: (value: string) => void }> {
  render() {
    const { item, onChange } = this.props;
    return (
      <div className="config-item">
        <div className="config-header">
          <label className="config-label">{item.name}</label>
          <div className="config-tooltip" title={item.description}>?</div>
        </div>
        <div className="config-control">
          <select value={item.value} onChange={(e) => onChange(e.target.value)}>
            {item.options?.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
      </div>
    );
  }
}

class StringConfig extends Component<{ item: ConfigItem; onChange: (value: string) => void }> {
  render() {
    const { item, onChange } = this.props;
    return (
      <div className="config-item">
        <div className="config-header">
          <label className="config-label">{item.name}</label>
          <div className="config-tooltip" title={item.description}>?</div>
        </div>
        <div className="config-control">
          <input className="config-input" type="text" value={item.value} onChange={(e) => onChange(e.target.value)} />
        </div>
      </div>
    );
  }
}

// 列表类型配置项组件
interface ListConfigState {
  newItem: string;
}

class ListConfig extends Component<{ item: ConfigItem; onChange: (value: string[]) => void }, ListConfigState> {
  state = {
    newItem: ''
  };
  
  handleAdd = () => {
    const { item, onChange } = this.props;
    const { newItem } = this.state;
    
    if (newItem.trim()) {
      onChange([...item.listItems || [], newItem.trim()]);
      this.setState({ newItem: '' });
    }
  };
  
  handleRemove = (index: number) => {
    const { item, onChange } = this.props;
    const newList = [...(item.listItems || [])];
    newList.splice(index, 1);
    onChange(newList);
  };
  
  render() {
    const { item } = this.props;
    const { newItem } = this.state;
    
    return (
      <div className="config-item">
        <div className="config-header">
          <label className="config-label">{item.name}</label>
          <div className="config-tooltip" title={item.description}>?</div>
        </div>
        <div className="config-control list-control">
          <div className="list-items">
            {(item.listItems || []).map((listItem, index) => (
              <div key={index} className="list-item">
                <span>{listItem}</span>
                <button onClick={() => this.handleRemove(index)}>删除</button>
              </div>
            ))}
          </div>
          <div className="list-add">
            <input
              type="text"
              value={newItem}
              onChange={(e) => this.setState({ newItem: e.target.value })}
              placeholder="添加新项"
            />
            <button onClick={this.handleAdd}>添加</button>
          </div>
        </div>
      </div>
    );
  }
}

// 字典类型配置项组件
interface DictConfigState {
  newKey: string;
  newValue: string;
}

class DictConfig extends Component<{ item: ConfigItem; onChange: (value: { key: string; value: string }[]) => void }, DictConfigState> {
  state = {
    newKey: '',
    newValue: ''
  };
  
  handleAdd = () => {
    const { item, onChange } = this.props;
    const { newKey, newValue } = this.state;
    
    if (newKey.trim() && newValue.trim()) {
      onChange([...item.items || [], { key: newKey.trim(), value: newValue.trim() }]);
      this.setState({ newKey: '', newValue: '' });
    }
  };
  
  handleRemove = (index: number) => {
    const { item, onChange } = this.props;
    const newItems = [...(item.items || [])];
    newItems.splice(index, 1);
    onChange(newItems);
  };
  
  handleEdit = (index: number, field: 'key' | 'value', value: string) => {
    const { item, onChange } = this.props;
    const newItems = [...(item.items || [])];
    newItems[index] = { ...newItems[index], [field]: value };
    onChange(newItems);
  };
  
  render() {
    const { item } = this.props;
    const { newKey, newValue } = this.state;
    
    return (
      <div className="config-item">
        <div className="config-header">
          <label className="config-label">{item.name}</label>
          <div className="config-tooltip" title={item.description}>?</div>
        </div>
        <div className="config-control dict-control">
          <table className="dict-table">
            <thead>
              <tr>
                <th>键</th>
                <th>值</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {(item.items || []).map((dictItem, index) => (
                <tr key={index}>
                  <td>
                    <input
                      type="text"
                      value={dictItem.key}
                      onChange={(e) => this.handleEdit(index, 'key', e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={dictItem.value}
                      onChange={(e) => this.handleEdit(index, 'value', e.target.value)}
                    />
                  </td>
                  <td>
                    <button onClick={() => this.handleRemove(index)}>删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="dict-add">
            <input
              type="text"
              value={newKey}
              onChange={(e) => this.setState({ newKey: e.target.value })}
              placeholder="键"
            />
            <input
              type="text"
              value={newValue}
              onChange={(e) => this.setState({ newValue: e.target.value })}
              placeholder="值"
            />
            <button onClick={this.handleAdd}>添加</button>
          </div>
        </div>
      </div>
    );
  }
}

// 配置项组件
class ConfigItemComponent extends Component<{ item: ConfigItem; onChange: (value: any) => void }> {
  render() {
    const { item, onChange } = this.props;
    
    switch (item.type) {
      case 'boolean':
        return <BooleanConfig item={item} onChange={onChange} />;
      case 'string':
        return <StringConfig item={item} onChange={onChange} />;
      case 'enum':
        return <EnumConfig item={item} onChange={onChange} />;
      case 'list':
        return <ListConfig item={item} onChange={onChange} />;
      case 'dict':
        return <DictConfig item={item} onChange={onChange} />;
      default:
        return <div>不支持的配置类型: {item.type}</div>;
    }
  }
}

// 配置组组件
class ConfigGroupComponent extends Component<{ 
  group: ConfigGroup; 
  onConfigChange: (groupTitle: string, itemIndex: number, value: any) => void 
}> {
  render() {
    const { group, onConfigChange } = this.props;
    
    return (
      <div className="config-group">
        <h2 className="config-group-title">{group.title}</h2>
        <div className="config-items">
          {group.items.map((item, itemIndex) => (
            <ConfigItemComponent
              key={item.name}
              item={item}
              onChange={(value) => onConfigChange(group.title, itemIndex, value)}
            />
          ))}
        </div>
      </div>
    );
  }
}

// 主配置页面组件
interface ProjectSettingsState {
  configData: ConfigGroup[];
}

interface ProjectSettingsProps {
  path: string;
}

class ProjectSettings extends Component<ProjectSettingsProps, ProjectSettingsState> {
  state = {
    configData: mockConfigData
  };
  
  componentDidMount() {
    // 根据 path 参数加载对应项目的配置
    console.log(`加载项目设置: ${this.props.path}`);
    // 这里可以添加根据 path 加载不同项目配置的逻辑
  }
  
  handleConfigChange = (groupTitle: string, itemIndex: number, value: any) => {
    this.setState(prevState => {
      return {
        configData: prevState.configData.map(group => {
          if (group.title === groupTitle) {
            const newItems = [...group.items];
            newItems[itemIndex] = { ...newItems[itemIndex], value };
            
            // 更新相应的数据字段
            if (newItems[itemIndex].type === 'list') {
              newItems[itemIndex].listItems = value;
            } else if (newItems[itemIndex].type === 'dict') {
              newItems[itemIndex].items = value;
            }
            
            return { ...group, items: newItems };
          }
          return group;
        })
      };
    });
  };
  
  render() {
    const { configData } = this.state;
    const { path } = this.props;
    
    return (
      <div className="project-settings">
        <h1 className="settings-title">项目设置: {path}</h1>
        <div className="settings-content">
          {configData.map((group, groupIndex) => (
            <ConfigGroupComponent
              key={group.title}
              group={group}
              onConfigChange={(groupTitle, itemIndex, value) => this.handleConfigChange(groupTitle, itemIndex, value)}
            />
          ))}
        </div>
      </div>
    );
  }
}

export class ProjectSettingsProvider implements UIProvider {
  getName(): string {
      return 'project_settings';
  }

  getUI(path: string): JSX.Element {
      return <ProjectSettings path={path} />;
  }
}

export default ProjectSettings;
