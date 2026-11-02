import type { Meta, StoryObj } from '@storybook/react';
import { ComponentTabRef } from './ComponentRef';
import './InternalComponents';

const meta = {
    title: 'Shared/Component playground', component: ComponentTabRef,
    render: args => <ComponentTabRef key={`${args.type}-${args.port}`} {...args} />,
    args: { name: 'value', type: 'builtins.str', port: 'input', root_path: '/mock', script_path: '/mock/demo.py' },
    argTypes: {
        type: { control: 'select', options: ['builtins.str', 'builtins.int', 'builtins.float', 'builtins.bool', 'ssui.base.Image', 'ssui.base.Video', 'ssui.base.Audio', 'typing.List[builtins.str]'] },
        port: { control: 'radio', options: ['input', 'output'] },
    },
} satisfies Meta<typeof ComponentTabRef>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Text: Story = {};
export const Integer: Story = { args: { type: 'builtins.int' } };
export const Boolean: Story = { args: { type: 'builtins.bool' } };
export const Image: Story = { args: { type: 'ssui.base.Image' } };
export const List: Story = { args: { type: 'typing.List[builtins.str]' } };
