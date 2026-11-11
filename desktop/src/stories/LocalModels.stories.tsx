import type { Meta, StoryObj } from '@storybook/react';
import LocalModels from '../components/ModelAdding/LocalModels';
import { MockModelsProvider } from './MockModelsProvider';

const meta = {
    title: 'Components/Model adding/Local models', component: LocalModels,
    args: { modelsProvider: new MockModelsProvider() },
} satisfies Meta<typeof LocalModels>;
export default meta;
type Story = StoryObj<typeof meta>;
const scan: Story['play'] = async ({ canvasElement }) => {
    canvasElement.querySelector<HTMLButtonElement>('button')!.click();
};
export const ChooseDirectory: Story = {};
export const ScanResults: Story = { play: scan };
export const EmptyDirectory: Story = { args: { modelsProvider: new MockModelsProvider([]) }, play: scan };
export const ScanError: Story = { args: { modelsProvider: new MockModelsProvider([], true) }, play: scan };
