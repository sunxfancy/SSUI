import type { Meta, StoryObj } from '@storybook/react';
import HuggingfaceModels from '../components/ModelAdding/HuggingfaceModels';
import { modelRoutes } from '../../../.storybook/mocks/models';

const meta = {
    title: 'Components/Model adding/Hugging Face', component: HuggingfaceModels,
    parameters: { offline: { routes: modelRoutes } },
} satisfies Meta<typeof HuggingfaceModels>;
export default meta;
type Story = StoryObj<typeof meta>;
const search: Story['play'] = async ({ canvasElement }) => {
    const input = canvasElement.querySelector('input')!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'demo/sdxl');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    // Allow React to apply the controlled input value before submitting.
    await new Promise(resolve => setTimeout(resolve, 0));
    canvasElement.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
};
export const Search: Story = {};
export const Results: Story = { play: search };
export const Empty: Story = { play: search, parameters: { offline: { routes: { 'GET /api/hf/models': [] } } } };
export const Error: Story = { play: search, parameters: { offline: { routes: {
    'GET /api/hf/models': () => new Response('Offline search failed', { status: 500 }),
} } } };
