export type ThemeMode = 'light' | 'dark' | 'system';

export type ResolvedTheme = 'light' | 'dark';

export interface UiConfig {
    /** 主题模式：跟随系统 / 浅色 / 深色 */
    theme: ThemeMode;
    /** FunctionalUI 打开时是否自动展开详细面板 */
    auto_open_details: boolean;
    /** 外部代码编辑器路径 */
    external_code_editor: string;
    /** Civitai 网站 Token */
    civitai_token: string;
}

export const DEFAULT_UI_CONFIG: UiConfig = {
    theme: 'system',
    auto_open_details: true,
    external_code_editor: '',
    civitai_token: '',
};

export type ConfigSaveStatus = 'saved' | 'saving' | 'unsaved';
