import type { Meta, StoryObj } from '@storybook/react';
import CivitaiModels from '../components/ModelAdding/CivitaiModels';
import { MockDownloaderProvider } from './MockModelsProvider';
import { modelRoutes } from '../../../.storybook/mocks/models';
const meta = {
    title: 'Components/Model sources', component: CivitaiModels,
    args: { onModelSelect: () => {}, downloaderProvider: new MockDownloaderProvider() },
    parameters: { offline: { routes: { 'GET /api/civitai/models': { items: [] } } } },
} satisfies Meta<typeof CivitaiModels>;
export default meta;
export const Results: StoryObj<typeof meta> = { parameters: { offline: { routes: modelRoutes } } };
export const Empty: StoryObj<typeof meta> = {};
export const Error: StoryObj<typeof meta> = { parameters: { offline: { routes: {
    'GET /api/civitai/models': () => new Response('Offline model service error', { status: 500 }),
} } } };
