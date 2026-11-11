import type { Meta, StoryObj } from '@storybook/react';
import { ViewSwitcher } from './ViewSwitcher';

const meta = {
    title: 'Functional/View switcher', component: ViewSwitcher,
    args: { path: '/mock/demo.py', currentView: 'functional' },
} satisfies Meta<typeof ViewSwitcher>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Python: Story = {};
export const Flow: Story = { args: { path: '/mock/demo.flow', currentView: 'workflow' } };
export const Unsupported: Story = { args: { path: '/mock/image.png' } };
