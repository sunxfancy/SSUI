import type { Meta, StoryObj } from '@storybook/react';
import Canvas from './App';
import { sampleImage } from '../../../.storybook/mocks/fixtures';

const meta = {
    title: 'Extensions/Image/Canvas', component: Canvas, args: { path: '/mock/drawing.py' },
    parameters: { layout: 'fullscreen', offline: { routes: {
        'POST /api/execute': [{ path: '/mock/generated.svg' }],
        'GET /file': () => fetch(sampleImage),
    } } },
} satisfies Meta<typeof Canvas>;
export default meta;
export const Drawing: StoryObj<typeof meta> = {};
