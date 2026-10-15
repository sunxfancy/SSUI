import type { Meta, StoryObj } from '@storybook/react';
import { ModelManager } from './ModelManager';
const meta = { title: 'Functional/Models', component: ModelManager, args: { path: '/mock' } } satisfies Meta<typeof ModelManager>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Installed: Story = {};
export const Empty: Story = { parameters: { offline: { routes: { 'GET /api/available_models': [] } } } };
export const Error: Story = { parameters: { offline: { routes: { 'GET /api/available_models': () => new Response(null, { status: 500 }) } } } };
