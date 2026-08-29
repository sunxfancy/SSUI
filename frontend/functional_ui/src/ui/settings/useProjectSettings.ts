import { useCallback, useMemo } from 'react';
import { useConfig, UiConfig } from '../../config';
import { settingsSchema } from './settingsSchema';
import { UserInputState } from './types';

const buildUserInput = (config: UiConfig): UserInputState => {
  const userInput: UserInputState = {};
  settingsSchema.forEach(group => {
    userInput[group.title] = {};
    group.items.forEach(item => {
      const value = (config as unknown as Record<string, unknown>)[item.key];
      userInput[group.title][item.name] = {
        value,
        ...(item.type === 'list' && { listItems: (value as string[]) ?? [] }),
        ...(item.type === 'dict' && { items: (value as { key: string; value: string }[]) ?? [] })
      };
    });
  });
  return userInput;
};

export const useProjectSettings = (_path: string) => {
  const {
    config,
    loaded,
    saveStatus,
    saveError,
    updateConfig,
    saveConfig,
    resetConfig,
  } = useConfig();

  const userInput = useMemo(() => buildUserInput(config), [config]);

  const handleConfigChange = useCallback((groupTitle: string, itemName: string, value: any) => {
    const item = settingsSchema
      .find(group => group.title === groupTitle)
      ?.items.find(entry => entry.name === itemName);
    if (!item?.key) {
      console.warn('未知配置项:', groupTitle, itemName);
      return;
    }
    updateConfig({ [item.key]: value } as Partial<UiConfig>);
  }, [updateConfig]);

  return {
    uiConfig: settingsSchema,
    userInput,
    loaded,
    saveStatus,
    saveError,
    handleConfigChange,
    saveConfig,
    resetConfig,
  };
};
