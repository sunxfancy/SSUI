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
        name: 'Civitai 访问令牌',
        type: 'string',
        description: '用于访问 Civitai API。令牌会保存在本机服务的配置文件中。',
        placeholder: '输入 API Token',
        sensitive: true
      },
      {
        key: 'external_code_editor',
        name: '外部代码编辑器',
        type: 'string',
        description: '打开代码文件时优先使用的编辑器可执行文件路径。留空则使用系统默认应用。',
        placeholder: '例如 C:\\Program Files\\Microsoft VS Code\\Code.exe'
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
        options: [
          { value: 'system', label: '跟随系统' },
          { value: 'light', label: '浅色' },
          { value: 'dark', label: '深色' }
        ]
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
