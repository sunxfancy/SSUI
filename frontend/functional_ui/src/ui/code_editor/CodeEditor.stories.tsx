import type { Meta, StoryObj } from '@storybook/react';
import { CodeEditor } from './CodeEditor';
const meta = {
    title: 'Functional/Code editor', component: CodeEditor, args: { path: '/mock/demo.py' },
    parameters: { layout: 'fullscreen', offline: { routes: {
        'GET /file': () => new Response('def preview(prompt: str) -> str:\n    return prompt\n'),
        'POST /files/upload_json': { success: true },
    } } },
} satisfies Meta<typeof CodeEditor>;
export default meta;
export const Editable: StoryObj<typeof meta> = {};
export const LoadError: StoryObj<typeof meta> = { parameters: { offline: { routes: {
    'GET /file': () => new Response('Offline file unavailable', { status: 404 }),
} } } };
