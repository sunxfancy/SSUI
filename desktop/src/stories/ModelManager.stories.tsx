import type { Meta, StoryObj } from '@storybook/react';
import { ModelManager } from '../components/ModelManager';
import { ModelManager as LegacyModelManager } from '../components/Model';
import { MockModelManagerProvider } from './MockModelManagerProvider';

const meta = {
    title: 'Components/Model manager', component: ModelManager,
    render: args => <ModelManager {...args} provider={new MockModelManagerProvider()} />,
} satisfies Meta<typeof ModelManager>;
export default meta;
export const Ready: StoryObj<typeof meta> = {};
export const Legacy: StoryObj<typeof meta> = {
    render: args => <LegacyModelManager {...args} provider={new MockModelManagerProvider()} />,
};
