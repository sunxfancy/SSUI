import React, { useState, useEffect, useCallback } from 'react';
import { ConfigItem, ConfigGroup } from './types';
import { mockConfigData } from './mockData';
import './ProjectSettings.css';
import { registerUIProvider, UIProvider } from '../UIProvider';
import { Message } from 'ssui_components';

// 布尔类型配置项组件
const BooleanConfig: React.FC<{ item: ConfigItem; onChange: (value: boolean) => void }> = ({ item, onChange }) => {
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
};

// 枚举类型配置项组件
const EnumConfig: React.FC<{ item: ConfigItem; onChange: (value: string) => void }> = ({ item, onChange }) => {
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
};

const StringConfig: React.FC<{ item: ConfigItem; onChange: (value: string) => void }> = ({ item, onChange }) => {
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
};

// 列表类型配置项组件
const ListConfig: React.FC<{ item: ConfigItem; onChange: (value: string[]) => void }> = ({ item, onChange }) => {
  const [newItem, setNewItem] = useState('');
  
  const handleAdd = () => {
    if (newItem.trim()) {
      onChange([...item.listItems || [], newItem.trim()]);
      setNewItem('');
    }
  };
  
  const handleRemove = (index: number) => {
    const newList = [...(item.listItems || [])];
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
          {(item.listItems || []).map((listItem, index) => (
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
const DictConfig: React.FC<{ item: ConfigItem; onChange: (value: { key: string; value: string }[]) => void }> = ({ item, onChange }) => {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  
  const handleAdd = () => {
    if (newKey.trim() && newValue.trim()) {
      onChange([...item.items || [], { key: newKey.trim(), value: newValue.trim() }]);
      setNewKey('');
      setNewValue('');
    }
  };
  
  const handleRemove = (index: number) => {
    const newItems = [...(item.items || [])];
    newItems.splice(index, 1);
    onChange(newItems);
  };
  
  const handleEdit = (index: number, field: 'key' | 'value', value: string) => {
    const newItems = [...(item.items || [])];
    newItems[index] = { ...newItems[index], [field]: value };
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
            {(item.items || []).map((dictItem, index) => (
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
const ConfigItemComponent: React.FC<{ item: ConfigItem; onChange: (value: any) => void }> = ({ item, onChange }) => {
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
};

// 配置组组件
const ConfigGroupComponent: React.FC<{ 
  group: ConfigGroup; 
  onConfigChange: (groupTitle: string, itemIndex: number, value: any) => void 
}> = ({ group, onConfigChange }) => {
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
};

// 主配置页面组件
interface ProjectSettingsProps {
  path: string;
}

const ProjectSettings: React.FC<ProjectSettingsProps> = ({ path }) => {
  const [configData, setConfigData] = useState<ConfigGroup[]>(mockConfigData);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [saveTimeout, setSaveTimeout] = useState<NodeJS.Timeout | null>(null);
  const [message] = useState(() => new Message());
  
  const loadConfig = useCallback(async () => {
    try {
      const response = await message.get(`file?path=${encodeURIComponent(path)}`);
      if (response) {
        const config = JSON.parse(response);
        setConfigData(config);
      }
    } catch (error) {
      console.error('加载配置失败:', error);
    }
  }, [path, message]);

  const saveConfig = useCallback(async () => {
    setSaveStatus('saving');
    try {
      await message.post('files/upload_json', {
        path: path,
        content: JSON.stringify(configData, null, 2)
      });
      setSaveStatus('saved');
    } catch (error) {
      console.error('保存失败:', error);
      setSaveStatus('unsaved');
    }
  }, [configData, path, message]);

  const debouncedSave = useCallback(() => {
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }
    setSaveStatus('unsaved');
    const timeout = setTimeout(() => {
      saveConfig();
    }, 2000);
    setSaveTimeout(timeout);
  }, [saveConfig, saveTimeout]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    return () => {
      if (saveTimeout) {
        clearTimeout(saveTimeout);
      }
    };
  }, [saveTimeout]);
  
  const handleConfigChange = (groupTitle: string, itemIndex: number, value: any) => {
    setConfigData(prevConfigData => 
      prevConfigData.map(group => {
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
    );
    debouncedSave();
  };
  
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
        {configData.map((group) => (
          <ConfigGroupComponent
            key={group.title}
            group={group}
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
