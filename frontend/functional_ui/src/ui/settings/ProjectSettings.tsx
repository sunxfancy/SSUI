import React, { useId, useState } from 'react';
import { ConfigGroup, ConfigItem } from './types';
import './ProjectSettings.css';
import { UIProvider } from '../UIProvider';
import { useProjectSettings } from './useProjectSettings';

interface ConfigControlProps<T> {
  item: ConfigItem;
  value: T;
  onChange: (value: T) => void;
}

const ConfigCopy: React.FC<{ item: ConfigItem; inputId?: string }> = ({ item, inputId }) => (
  <div className="config-copy">
    <label className="config-label" htmlFor={inputId}>{item.name}</label>
    <p className="config-description">{item.description}</p>
  </div>
);

const BooleanConfig: React.FC<ConfigControlProps<boolean>> = ({ item, value, onChange }) => {
  const inputId = useId();
  return (
    <div className="config-item config-item-toggle">
      <ConfigCopy item={item} inputId={inputId} />
      <label className="toggle-control" htmlFor={inputId}>
        <input id={inputId} type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
        <span className="toggle-track" aria-hidden="true"><span /></span>
      </label>
    </div>
  );
};

const EnumConfig: React.FC<ConfigControlProps<string>> = ({ item, value, onChange }) => {
  const inputId = useId();
  return (
    <div className="config-item">
      <ConfigCopy item={item} inputId={inputId} />
      <div className="config-control">
        <select id={inputId} value={value ?? ''} onChange={(event) => onChange(event.target.value)}>
          {item.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>
    </div>
  );
};

const StringConfig: React.FC<ConfigControlProps<string>> = ({ item, value, onChange }) => {
  const inputId = useId();
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="config-item">
      <ConfigCopy item={item} inputId={inputId} />
      <div className="config-control config-input-row">
        <input
          id={inputId}
          className="config-input"
          type={item.sensitive && !revealed ? 'password' : 'text'}
          value={value ?? ''}
          placeholder={item.placeholder}
          autoComplete={item.sensitive ? 'off' : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
        {item.sensitive && (
          <button className="secondary-button reveal-button" type="button" onClick={() => setRevealed(current => !current)}>
            {revealed ? '隐藏' : '显示'}
          </button>
        )}
      </div>
    </div>
  );
};

const ListConfig: React.FC<ConfigControlProps<string[]>> = ({ item, value = [], onChange }) => {
  const [newItem, setNewItem] = useState('');
  const addItem = () => {
    const nextItem = newItem.trim();
    if (nextItem) {
      onChange([...value, nextItem]);
      setNewItem('');
    }
  };
  return (
    <div className="config-item">
      <ConfigCopy item={item} />
      <div className="config-control list-control">
        <div className="list-items">
          {value.map((entry, index) => (
            <div key={`${entry}-${index}`} className="list-item">
              <span>{entry}</span>
              <button type="button" onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}>删除</button>
            </div>
          ))}
        </div>
        <div className="list-add">
          <input value={newItem} onChange={(event) => setNewItem(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && addItem()} placeholder="添加新项" />
          <button type="button" onClick={addItem}>添加</button>
        </div>
      </div>
    </div>
  );
};

type DictEntry = { key: string; value: string };

const DictConfig: React.FC<ConfigControlProps<DictEntry[]>> = ({ item, value = [], onChange }) => {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const addItem = () => {
    if (newKey.trim() && newValue.trim()) {
      onChange([...value, { key: newKey.trim(), value: newValue.trim() }]);
      setNewKey('');
      setNewValue('');
    }
  };
  const editItem = (index: number, field: keyof DictEntry, fieldValue: string) => {
    onChange(value.map((entry, itemIndex) => itemIndex === index ? { ...entry, [field]: fieldValue } : entry));
  };
  return (
    <div className="config-item">
      <ConfigCopy item={item} />
      <div className="config-control dict-control">
        <table className="dict-table">
          <thead><tr><th>键</th><th>值</th><th>操作</th></tr></thead>
          <tbody>
            {value.map((entry, index) => (
              <tr key={index}>
                <td><input value={entry.key} onChange={(event) => editItem(index, 'key', event.target.value)} /></td>
                <td><input value={entry.value} onChange={(event) => editItem(index, 'value', event.target.value)} /></td>
                <td><button type="button" onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}>删除</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="dict-add">
          <input value={newKey} onChange={(event) => setNewKey(event.target.value)} placeholder="键" />
          <input value={newValue} onChange={(event) => setNewValue(event.target.value)} placeholder="值" />
          <button type="button" onClick={addItem}>添加</button>
        </div>
      </div>
    </div>
  );
};

const ConfigItemComponent: React.FC<ConfigControlProps<any>> = (props) => {
  switch (props.item.type) {
    case 'boolean': return <BooleanConfig {...props} />;
    case 'string': return <StringConfig {...props} />;
    case 'enum': return <EnumConfig {...props} />;
    case 'list': return <ListConfig {...props} />;
    case 'dict': return <DictConfig {...props} />;
  }
};

const ConfigGroupComponent: React.FC<{
  group: ConfigGroup;
  userInput: { [key: string]: any };
  onConfigChange: (groupTitle: string, itemName: string, value: any) => void;
}> = ({ group, userInput, onConfigChange }) => (
  <section className="config-group">
    <h2 className="config-group-title">{group.title}</h2>
    <div className="config-items">
      {group.items.map((item) => (
        <ConfigItemComponent key={item.key} item={item} value={userInput[item.name]?.value} onChange={(value) => onConfigChange(group.title, item.name, value)} />
      ))}
    </div>
  </section>
);

const ProjectSettings: React.FC<{ path: string }> = ({ path }) => {
  const settings = useProjectSettings(path);
  const statusText = {
    saved: '所有更改已保存',
    saving: '正在保存…',
    unsaved: '等待保存',
    error: '保存失败',
  }[settings.saveStatus];

  return (
    <div className="project-settings">
      <header className="settings-header">
        <div>
          <div className="settings-eyebrow">SSUI / PREFERENCES</div>
          <h1 className="settings-title">通用配置</h1>
          <p className="settings-subtitle">管理界面外观、工作方式和外部服务。更改会自动保存到本机。</p>
        </div>
        <div className="settings-actions">
          <button className="secondary-button" type="button" onClick={settings.resetConfig} disabled={!settings.loaded || settings.saveStatus === 'saving'}>恢复默认值</button>
          <div className={`save-status ${settings.saveStatus}`} role="status" aria-live="polite"><span className="status-dot" />{statusText}</div>
        </div>
      </header>
      {settings.saveStatus === 'error' && (
        <div className="save-error" role="alert">
          <div><strong>配置尚未写入服务端</strong><span>{settings.saveError || '请确认服务正在运行后重试。本地修改已保留。'}</span></div>
          <button type="button" onClick={() => void settings.saveConfig()}>重试保存</button>
        </div>
      )}
      {!settings.loaded ? <div className="settings-loading" role="status">正在加载配置…</div> : (
        <div className="settings-content">
          {settings.uiConfig.map((group) => <ConfigGroupComponent key={group.title} group={group} userInput={settings.userInput[group.title] || {}} onConfigChange={settings.handleConfigChange} />)}
        </div>
      )}
    </div>
  );
};

export class ProjectSettingsProvider implements UIProvider {
  getName(): string { return 'project_settings'; }
  getUI(path: string): JSX.Element { return <ProjectSettings path={path} />; }
}

export default ProjectSettings;
