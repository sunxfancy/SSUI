import type { StorybookConfig } from '@storybook/react-vite';
import { mergeConfig } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';
import { realpathSync } from 'fs';

const dirname = path.dirname(fileURLToPath(import.meta.url));

const config: StorybookConfig = {
    framework: '@storybook/react-vite',
    stories: [
        '../desktop/src/**/*.stories.@(js|jsx|mjs|ts|tsx)',
        '../frontend/*/src/**/*.stories.@(js|jsx|mjs|ts|tsx)',
        '../extensions/*/**/*.stories.@(js|jsx|mjs|ts|tsx)',
    ],
    addons: ['@storybook/addon-essentials'],
    core: {
        builder: '@storybook/builder-vite', // 👈 The builder enabled here.
    },
    async viteFinal(config) {
        // Storybook owns its server; never inherit application backend proxies.
        config.server = { ...config.server, proxy: {} };
        return mergeConfig(config, {
            server: {
                fs: {
                    // Worktrees may share dependencies through a junction.
                    allow: [path.resolve(dirname, '..'), realpathSync(path.resolve(dirname, '../node_modules'))],
                },
            },
            resolve: {
                alias: Object.entries({
                    'ssui_components': path.resolve(dirname, '../frontend/ssui_components/src/index.ts'),
                    'axios': path.resolve(dirname, './mocks/axios.ts'),
                    '@tauri-apps/api/core': path.resolve(dirname, './mocks/tauri.ts'),
                    '@tauri-apps/api/event': path.resolve(dirname, './mocks/tauri.ts'),
                    '@tauri-apps/plugin-store': path.resolve(dirname, './mocks/tauri.ts'),
                    '@tauri-apps/plugin-os': path.resolve(dirname, './mocks/tauri.ts'),
                    '@tauri-apps/plugin-process': path.resolve(dirname, './mocks/tauri.ts'),
                    '@tauri-apps/api/path': path.resolve(dirname, './mocks/tauriPath.ts'),
                    '@tauri-apps/plugin-fs': path.resolve(dirname, './mocks/tauriFs.ts'),
                    '@tauri-apps/plugin-dialog': path.resolve(dirname, './mocks/tauriDialog.ts'),
                }).map(([find, replacement]) => ({ find: new RegExp(`^${find.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`), replacement })),
            },
        });
    },
};

export default config;
