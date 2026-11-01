// 配置项类型定义
export type ConfigType = 'boolean' | 'string' | 'enum' | 'list' | 'dict';

// 配置项接口
export interface ConfigItem {
  /** 对应持久化配置中的字段名（如 theme、auto_open_details） */
  key: string;
  name: string;
  type: ConfigType;
  description: string;
  placeholder?: string;
  sensitive?: boolean;
  value?: any;
  options?: { value: string; label: string }[]; // 用于enum类型
  items?: { key: string; value: string }[]; // 用于dict类型
  listItems?: string[]; // 用于list类型
}

// 配置组接口
export interface ConfigGroup {
  title: string;
  items: ConfigItem[];
}

// 用户输入状态相关类型
export interface UserInputValue {
  value: any;
  listItems?: string[];
  items?: { key: string; value: string }[];
}

export interface UserInputState {
  [groupTitle: string]: {
    [itemName: string]: UserInputValue;
  };
}

// 完整的配置状态
export interface ProjectSettingsState {
  uiConfig: ConfigGroup[];  // 界面配置
  userInput: UserInputState;  // 用户输入状态
  saveStatus: 'saved' | 'saving' | 'unsaved' | 'error';
}
