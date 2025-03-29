import type { StorybookConfig } from '@storybook/react-vite';
 
const config: StorybookConfig = {
    framework: '@storybook/react-vite',
    stories: ['../src/stories/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
    addons: ['@storybook/addon-essentials'],
    core: {
        builder: '@storybook/builder-vite', // 👈 The builder enabled here.
    },
};

export default config;
