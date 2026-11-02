import type { Meta, StoryObj } from '@storybook/react';
import ProjectSettings from './ProjectSettings';
import { ConfigProvider } from '../../config/ConfigContext';

const meta = {
    title: 'Functional/Settings', component: ProjectSettings,
    args: { path: '/mock' },
    decorators: [(Story) => <ConfigProvider><Story /></ConfigProvider>],
} satisfies Meta<typeof ProjectSettings>;
export default meta;
export const Editable: StoryObj<typeof meta> = {};
export const SaveError: StoryObj<typeof meta> = { parameters: { offline: { routes: {
    'POST /config/': () => { throw new Error('Offline save failed'); },
} } } };
