// 配置项类型定义
export type ConfigType = 'boolean' | 'string' | 'enum' | 'list' | 'dict';

// 配置项接口
export interface ConfigItem {
  name: string;
  type: ConfigType;
  description: string;
  value?: any;
  options?: string[]; // 用于enum类型
  items?: { key: string; value: string }[]; // 用于dict类型
  listItems?: string[]; // 用于list类型
}

// 配置组接口
export interface ConfigGroup {
  title: string;
  items: ConfigItem[];
} 