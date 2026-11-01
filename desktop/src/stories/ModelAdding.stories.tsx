import type { Meta, StoryObj } from '@storybook/react';
import ModelAddingPage from '../components/ModelAdding';
import { MockModelsProvider, MockDownloaderProvider } from './MockModelsProvider';
import { modelRoutes } from '../../../.storybook/mocks/models';

const meta = {
    title: 'Components/Model adding', component: ModelAddingPage,
    parameters: { layout: 'fullscreen', offline: { routes: modelRoutes } },
    args: { modelsProvider: new MockModelsProvider(), downloaderProvider: new MockDownloaderProvider() },
    render: args => <ModelAddingPage key={args.initialTab} {...args} />,
} satisfies Meta<typeof ModelAddingPage>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Presets: Story = {};
export const Civitai: Story = { args: { initialTab: 'civitai' } };
export const HuggingFace: Story = { args: { initialTab: 'huggingface' } };
export const Local: Story = { args: { initialTab: 'local' } };
