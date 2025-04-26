import { ConfigGroup } from './types';

// 模拟配置数据
export const mockConfigData: ConfigGroup[] = [
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
  },
  {
    title: '功能设置',
    items: [
      {
        name: '快捷键列表',
        type: 'list',
        description: '自定义快捷键列表',
        value: ['Ctrl+S', 'Ctrl+Z', 'Ctrl+Y'],
        listItems: ['Ctrl+S', 'Ctrl+Z', 'Ctrl+Y']
      },
      {
        name: '环境变量',
        type: 'dict',
        description: '配置环境变量',
        value: { 'API_URL': 'http://localhost:3000', 'DEBUG': 'true' },
        items: [
          { key: 'API_URL', value: 'http://localhost:3000' },
          { key: 'DEBUG', value: 'true' }
        ]
      }
    ]
  }
]; 