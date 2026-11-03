import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { MotionClipPreview } from './MotionClipPreview';

function Preview({ loaded = true }: { loaded?: boolean }) {
    const ref = React.useRef<MotionClipPreview>(null);
    React.useEffect(() => { if (loaded) void ref.current?.onUpdate({ path: '/mock/motion.json' }); }, [loaded]);
    return <div style={{ maxWidth: 600 }}><MotionClipPreview ref={ref} /></div>;
}
const clip = {
    schema: 'ssui.motion.clip/v1', fps: 24, units: 'meters', coordinate_system: 'Y-up;+Z-forward',
    joint_names: ['root', 'spine', 'head', 'left', 'right'], parents: [-1, 0, 1, 1, 1],
    positions: Array.from({ length: 48 }, (_, i) => [
        [i / 48, 0, 0], [i / 48, 0.8, 0], [i / 48, 1.5, 0],
        [i / 48 - 0.5, 0.8 + Math.sin(i / 8) * 0.3, 0], [i / 48 + 0.5, 0.8, 0],
    ]),
};
const meta = {
    title: 'Shared/Motion playback', component: Preview,
    parameters: { offline: { routes: { 'GET /file': clip } } },
} satisfies Meta<typeof Preview>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Ready: Story = {};
export const Empty: Story = { args: { loaded: false } };
export const Loading: Story = { parameters: { offline: { delay: 30000 } } };
export const Error: Story = { parameters: { offline: { routes: {
    'GET /file': () => new Response('Unavailable', { status: 500 }),
} } } };
export const InvalidData: Story = { parameters: { offline: { routes: { 'GET /file': { ...clip, parents: [0] } } } } };
