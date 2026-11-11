import type { Meta, StoryObj } from '@storybook/react';
import PresetModels from '../components/ModelAdding/PresetModels';
import { modelRoutes } from '../../../.storybook/mocks/models';
const meta = {
    title: 'Components/Model adding/Presets', component: PresetModels,
    parameters: { offline: { routes: modelRoutes } },
} satisfies Meta<typeof PresetModels>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Bundles: Story = {};
export const Empty: Story = { parameters: { offline: { routes: { 'GET /api/preset_models': { items: [] } } } } };
export const Loading: Story = { parameters: { offline: { delay: 30000 } } };
