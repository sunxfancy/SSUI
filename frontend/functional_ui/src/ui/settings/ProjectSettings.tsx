import React, { useState, useEffect, useCallback } from 'react';
import { ConfigItem, ConfigGroup } from './types';
import './ProjectSettings.css';
import { registerUIProvider, UIProvider } from '../UIProvider';
import { Message } from 'ssui_components';
import { useProjectSettings } from './useProjectSettings';

// 布尔类型配置项组件
const BooleanConfig: React.FC<{ item: ConfigItem; value: boolean; onChange: (value: boolean) => void }> = ({ item, value, onChange }) => {
  return (
    <div className="config-item">
      <div className="config-header">
        <label className="config-label">{item.name}</label>
        <div className="config-tooltip" title={item.description}>?</div>
      </div>
      <div className="config-control">
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
        />
      </div>
    </div>
  );
};

// 枚举类型配置项组件
const EnumConfig: React.FC<{ item: ConfigItem; value: string; onChange: (value: string) => void }> = ({ item, value, onChange }) => {
  return (
    <div className="config-item">
      <div className="config-header">
        <label className="config-label">{item.name}</label>
        <div className="config-tooltip" title={item.description}>?</div>
      </div>
      <div className="config-control">
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {item.options?.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </div>
    </div>
  );
};

const StringConfig: React.FC<{ item: ConfigItem; value: string; onChange: (value: string) => void }> = ({ item, value, onChange }) => {
  return (
    <div className="config-item">
      <div className="config-header">
        <label className="config-label">{item.name}</label>
        <div className="config-tooltip" title={item.description}>?</div>
      </div>
      <div className="config-control">
        <input className="config-input" type="text" value={value} onChange={(e) => onChange(e.target.value)} />
      </div>
    </div>
  );
};

// 列表类型配置项组件
const ListConfig: React.FC<{ item: ConfigItem; value: string[]; onChange: (value: string[]) => void }> = ({ item, value, onChange }) => {
  const [newItem, setNewItem] = useState('');
  
  const handleAdd = () => {
    if (newItem.trim()) {
      onChange([...value, newItem.trim()]);
      setNewItem('');
    }
  };
  
  const handleRemove = (index: number) => {
    const newList = [...value];
    newList.splice(index, 1);
    onChange(newList);
  };
  
  return (
    <div className="config-item">
      <div className="config-header">
        <label className="config-label">{item.name}</label>
        <div className="config-tooltip" title={item.description}>?</div>
      </div>
      <div className="config-control list-control">
        <div className="list-items">
          {value.map((listItem, index) => (
            <div key={index} className="list-item">
              <span>{listItem}</span>
              <button onClick={() => handleRemove(index)}>删除</button>
            </div>
          ))}
        </div>
        <div className="list-add">
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            placeholder="添加新项"
          />
          <button onClick={handleAdd}>添加</button>
        </div>
      </div>
    </div>
  );
};

// 字典类型配置项组件
const DictConfig: React.FC<{ 
  item: ConfigItem; 
  value: { key: string; value: string }[]; 
  onChange: (value: { key: string; value: string }[]) => void 
}> = ({ item, value, onChange }) => {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  
  const handleAdd = () => {
    if (newKey.trim() && newValue.trim()) {
      onChange([...value, { key: newKey.trim(), value: newValue.trim() }]);
      setNewKey('');
      setNewValue('');
    }
  };
  
  const handleRemove = (index: number) => {
    const newItems = [...value];
    newItems.splice(index, 1);
    onChange(newItems);
  };
  
  const handleEdit = (index: number, field: 'key' | 'value', newValue: string) => {
    const newItems = [...value];
    newItems[index] = { ...newItems[index], [field]: newValue };
    onChange(newItems);
  };
  
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
            {value.map((dictItem, index) => (
              <tr key={index}>
                <td>
                  <input
                    type="text"
                    value={dictItem.key}
                    onChange={(e) => handleEdit(index, 'key', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={dictItem.value}
                    onChange={(e) => handleEdit(index, 'value', e.target.value)}
                  />
                </td>
                <td>
                  <button onClick={() => handleRemove(index)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="dict-add">
          <input
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="键"
          />
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="值"
          />
          <button onClick={handleAdd}>添加</button>
        </div>
      </div>
    </div>
  );
};

// 配置项组件
const ConfigItemComponent: React.FC<{ 
  item: ConfigItem; 
  value: any;
  onChange: (value: any) => void 
}> = ({ item, value, onChange }) => {
  switch (item.type) {
    case 'boolean':
      return <BooleanConfig item={item} value={value} onChange={onChange} />;
    case 'string':
      return <StringConfig item={item} value={value} onChange={onChange} />;
    case 'enum':
      return <EnumConfig item={item} value={value} onChange={onChange} />;
    case 'list':
      return <ListConfig item={item} value={value} onChange={onChange} />;
    case 'dict':
      return <DictConfig item={item} value={value} onChange={onChange} />;
    default:
      return <div>不支持的配置类型: {item.type}</div>;
  }
};

// 配置组组件
const ConfigGroupComponent: React.FC<{ 
  group: ConfigGroup;
  userInput: { [key: string]: any };
  onConfigChange: (groupTitle: string, itemName: string, value: any) => void 
}> = ({ group, userInput, onConfigChange }) => {
  return (
    <div className="config-group">
      <h2 className="config-group-title">{group.title}</h2>
      <div className="config-items">
        {group.items.map((item) => (
          <ConfigItemComponent
            key={item.name}
            item={item}
            value={userInput[item.name]?.value}
            onChange={(value) => onConfigChange(group.title, item.name, value)}
          />
        ))}
      </div>
    </div>
  );
};

// 主配置页面组件
interface ProjectSettingsProps {
  path: string;
}

const ProjectSettings: React.FC<ProjectSettingsProps> = ({ path }) => {
  const { uiConfig, userInput, saveStatus, handleConfigChange } = useProjectSettings(path);
  
  return (
    <div className="project-settings">
      <div className="settings-header">
        <h1 className="settings-title">项目设置: {path}</h1>
        <div className={`save-status ${saveStatus}`}>
          {saveStatus === 'saved' && '已保存'}
          {saveStatus === 'saving' && '保存中...'}
          {saveStatus === 'unsaved' && '未保存'}
        </div>
      </div>
      <div className="settings-content">
        {uiConfig.map((group) => (
          <ConfigGroupComponent
            key={group.title}
            group={group}
            userInput={userInput[group.title] || {}}
            onConfigChange={handleConfigChange}
          />
        ))}
      </div>
    </div>
  );
};

export class ProjectSettingsProvider implements UIProvider {
  getName(): string {
    return 'project_settings';
  }

  getUI(path: string): JSX.Element {
    return <ProjectSettings path={path} />;
  }
}

export default ProjectSettings;
