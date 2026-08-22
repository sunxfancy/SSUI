import { ConfigGroup } from './types';

/**
 * 设置页面的真实配置 schema。
 * 每个配置项的 key 对应持久化配置（UiConfig）中的字段，
 * 通过服务端 `/config/` 读写，而不是 mock 数据。
 */
export const settingsSchema: ConfigGroup[] = [
  {
    title: '外部服务',
    items: [
      {
        key: 'civitai_token',
        name: "Civitai网站Token",
        type: "string",
        description: "Civitai网站的Token"
      },
      {
        key: 'external_code_editor',
        name: "外部代码编辑器",
        type: "string",
        description: "外部代码编辑器路径"
      }
    ]
  },
  {
    title: '界面设置',
    items: [
      {
        key: 'theme',
        name: '主题颜色',
        type: 'enum',
        description: '选择界面主题颜色：跟随系统 / 浅色 / 深色',
        options: ['system', 'light', 'dark']
      },
      {
        key: 'auto_open_details',
        name: '自动打开详细面板',
        type: 'boolean',
        description: '在FunctionalUI下，页面打开时自动显示详细面板页面'
      }
    ]
  }
];
