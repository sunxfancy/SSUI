import { ConfigGroup } from './types';

// 模拟配置数据
export const mockConfigData: ConfigGroup[] = [
  {
    title: '外部服务',
    items: [
      {
        name: "Civitai网站Token",
        type: "string",
        description: "Civitai网站的Token",
        value: ""
      },
      {
        name: "外部代码编辑器",
        type: "string",
        description: "外部代码编辑器路径",
        value: ""
      }
    ]
  },
  {
    title: '界面设置',
    items: [
      {
        name: '自动打开详细面板',
        type: 'boolean',
        description: '在FunctionalUI下，页面打开时自动显示详细面板页面',
        value: true
      },
      {
        name: '主题颜色',
        type: 'enum',
        description: '选择界面主题颜色',
        value: 'light',
        options: ['light', 'dark', 'system']
      }
    ]
  }
]; 