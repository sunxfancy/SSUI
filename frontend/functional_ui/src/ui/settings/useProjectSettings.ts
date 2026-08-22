import { useState, useCallback, useEffect, useRef } from 'react';
import { ConfigGroup, ProjectSettingsState, UserInputState } from './types';
import { Message } from 'ssui_components';
import { mockConfigData } from './mockData';

// 初始化用户输入状态
const initializeUserInput = (config: ConfigGroup[]): UserInputState => {
  const userInput: UserInputState = {};
  
  config.forEach(group => {
    userInput[group.title] = {};
    group.items.forEach(item => {
      let initialValue: any;
      switch (item.type) {
        case 'boolean':
          initialValue = false;
          break;
        case 'string':
          initialValue = '';
          break;
        case 'enum':
          initialValue = item.options?.[0] || '';
          break;
        case 'list':
          initialValue = [];
          break;
        case 'dict':
          initialValue = [];
          break;
        default:
          initialValue = null;
      }
      
      userInput[group.title][item.name] = {
        value: initialValue,
        ...(item.type === 'list' && { listItems: [] }),
        ...(item.type === 'dict' && { items: [] })
      };
    });
  });
  
  return userInput;
};

export const useProjectSettings = (path: string) => {
  const [state, setState] = useState<ProjectSettingsState>(() => ({
    uiConfig: mockConfigData,
    userInput: initializeUserInput(mockConfigData),
    saveStatus: 'saved'
  }));
  const [saveTimeout, setSaveTimeout] = useState<NodeJS.Timeout | null>(null);
  const [message] = useState(() => new Message());
  const stateRef = useRef(state);
  stateRef.current = state;

  const loadConfig = useCallback(async () => {
    try {
      const response = await message.get(`file?path=${encodeURIComponent(path)}`);
      console.log('response', response);
      if (response) {
        const loadedUserInput = response;
        const mergedUserInput = {
          ...initializeUserInput(mockConfigData),
          ...loadedUserInput
        };
        setState(prev => ({ ...prev, userInput: mergedUserInput }));
      }
    } catch (error) {
      console.error('加载配置失败:', error);
    }
  }, [path, message]);

  const saveConfig = useCallback(async () => {
    setState(prev => ({ ...prev, saveStatus: 'saving' }));
    try {
      // 使用最新的状态进行保存
      const currentState = stateRef.current;
      await message.post('files/upload_json', {
        path: path,
        content: JSON.stringify(currentState.userInput, null, 2)
      });
      setState(prev => ({ ...prev, saveStatus: 'saved' }));
    } catch (error) {
      console.error('保存失败:', error);
      setState(prev => ({ ...prev, saveStatus: 'unsaved' }));
    }
  }, [path, message]);

  const debouncedSave = useCallback(() => {
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }
    setState(prev => ({ ...prev, saveStatus: 'unsaved' }));
    const timeout = setTimeout(() => {
      saveConfig();
    }, 2000);
    setSaveTimeout(timeout);
  }, [saveConfig, saveTimeout]);

  const handleConfigChange = useCallback((groupTitle: string, itemName: string, value: any) => {
    setState(prev => {
      const newState = {
        ...prev,
        userInput: {
          ...prev.userInput,
          [groupTitle]: {
            ...prev.userInput[groupTitle],
            [itemName]: {
              value,
              ...(Array.isArray(value) && { listItems: value }),
              ...(typeof value === 'object' && value !== null && { items: value })
            }
          }
        }
      };
      // 立即更新ref，确保保存时使用最新状态
      stateRef.current = newState;
      return newState;
    });
    debouncedSave();
  }, [debouncedSave]);

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

  return {
    uiConfig: state.uiConfig,
    userInput: state.userInput,
    saveStatus: state.saveStatus,
    handleConfigChange
  };
}; 