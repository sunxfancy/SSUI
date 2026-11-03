import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { ConversationView } from './ConversationView';
import { SessionProvider } from './SessionState';

const script = { root_path: '/mock', functions: { chat: {
    params: { prompt: 'builtins.str', history: 'typing.List[builtins.str]', model: 'ssui_llm.Text.TextModel' },
    returns: ['builtins.str'],
    conversation: { prompt_param: 'prompt', context_param: 'history', context_kind: 'pairs', context_output: null },
} } };
const meta = {
    title: 'Functional/Conversation', component: ConversationView,
    args: { path: '/mock/chat.py' },
    decorators: [Story => <SessionProvider><Story /></SessionProvider>],
    parameters: { layout: 'fullscreen', offline: { routes: {
        'GET /api/script': script,
        'POST /api/execute': ['这是离线演示回复。可以继续提问，或点击新对话重置上下文。'],
    } } },
} satisfies Meta<typeof ConversationView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Ready: Story = {};
export const Loading: Story = { parameters: { offline: { delay: 30000 } } };
export const Unsupported: Story = { parameters: { offline: { routes: {
    'GET /api/script': { root_path: '/mock', functions: {} },
} } } };
export const LoadError: Story = { parameters: { offline: { routes: {
    'GET /api/script': () => new Response('Unavailable', { status: 500 }),
} } } };
export const SendError: Story = { parameters: { offline: { routes: {
    'POST /api/execute': () => new Response('离线演示：生成失败，可重试发送。', { status: 500 }),
} } } };
export const InvalidReply: Story = { parameters: { offline: { routes: {
    'POST /api/execute': [42],
} } } };
