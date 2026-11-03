import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { ContextMenu } from './ContextMenu';

function Demo() {
    const [position, setPosition] = React.useState<{ x: number; y: number }>();
    const [selected, setSelected] = React.useState('右键点击此区域');
    return <div style={{ height: 400, padding: 32, background: '#edf2f7' }}
        onContextMenu={event => { event.preventDefault(); setPosition({ x: event.clientX, y: event.clientY }); }}>
        {selected}
        {position && <ContextMenu {...position} onClose={() => setPosition(undefined)} items={[
            { label: '打开', icon: 'document-open', onClick: () => setSelected('已打开') },
            { label: '不可用', disabled: true },
            { label: '删除', intent: 'danger', dividerBefore: true, onClick: () => setSelected('已删除') },
        ]} />}
    </div>;
}
const meta = { title: 'Shared/Context menu', component: Demo } satisfies Meta<typeof Demo>;
export default meta;
export const Interactive: StoryObj<typeof meta> = {};
