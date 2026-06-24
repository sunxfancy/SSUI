import type { StorybookConfig } from '@storybook/react-vite';
import { mergeConfig } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';

const dirname = path.dirname(fileURLToPath(import.meta.url));

const config: StorybookConfig = {
    framework: '@storybook/react-vite',
    stories: ['../src/stories/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
    addons: ['@storybook/addon-essentials'],
    core: {
        builder: '@storybook/builder-vite', // 👈 The builder enabled here.
    },
    async viteFinal(config) {
        return mergeConfig(config, {
            resolve: {
                alias: {
                    '@tauri-apps/api/path': path.resolve(dirname, '../src/stories/mocks/tauriPath.ts'),
                    '@tauri-apps/plugin-fs': path.resolve(dirname, '../src/stories/mocks/tauriFs.ts'),
                    '@tauri-apps/plugin-dialog': path.resolve(dirname, '../src/stories/mocks/tauriDialog.ts'),
                },
            },
        });
    },
};

export default config;
