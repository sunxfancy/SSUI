import { ResolvedTheme, ThemeMode } from './types';

const DARK_MEDIA_QUERY = '(prefers-color-scheme: dark)';

function getSystemTheme(): ResolvedTheme {
    if (typeof window !== 'undefined' && window.matchMedia) {
        return window.matchMedia(DARK_MEDIA_QUERY).matches ? 'dark' : 'light';
    }
    return 'light';
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
    if (mode === 'system') {
        return getSystemTheme();
    }
    return mode;
}

/**
 * 将主题应用到整个文档：
 * - `data-theme` 属性驱动 CSS 变量（浅色 / 深色两套色板）
 * - `bp5-dark` 类让 Blueprint 组件（卡片、输入框、弹层等）跟随主题
 */
export function applyTheme(mode: ThemeMode): ResolvedTheme {
    const resolved = resolveTheme(mode);
    const root = document.documentElement;
    root.dataset.theme = resolved;

    const isDark = resolved === 'dark';
    root.classList.toggle('bp5-dark', isDark);
    document.body.classList.toggle('bp5-dark', isDark);
    return resolved;
}

export function watchSystemTheme(onChange: (theme: ResolvedTheme) => void): () => void {
    if (typeof window === 'undefined' || !window.matchMedia) {
        return () => {};
    }
    const media = window.matchMedia(DARK_MEDIA_QUERY);
    const handler = (event: MediaQueryListEvent) => {
        onChange(event.matches ? 'dark' : 'light');
    };
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
}
