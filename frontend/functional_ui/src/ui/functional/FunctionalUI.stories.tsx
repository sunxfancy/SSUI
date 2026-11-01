import type { Meta, StoryObj } from '@storybook/react';
import FunctionalUI from './FunctionalUI';

const meta = {
    title: 'Functional/Function console', component: FunctionalUI,
    parameters: { layout: 'fullscreen' }, args: { path: '/mock/demo.py' },
} satisfies Meta<typeof FunctionalUI>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Ready: Story = {};
export const Advanced: Story = { args: { autoOpenDetails: true } };
export const Loading: Story = { parameters: { offline: { delay: 30000 } } };
export const Empty: Story = { parameters: { offline: { routes: { 'GET /api/script': { root_path: '/mock', functions: {} } } } } };
export const Error: Story = { parameters: { offline: { routes: { 'GET /api/script': () => new Response('Script unavailable', { status: 500 }) } } } };
export const RunError: Story = { parameters: { offline: { routes: { 'POST /api/execute': () => new Response('Offline executor failure', { status: 500 }) } } } };
