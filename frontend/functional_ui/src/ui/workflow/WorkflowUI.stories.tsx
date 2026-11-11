import type { Meta, StoryObj } from '@storybook/react';
import WorkflowUI from './WorkflowUI';
const meta = { title: 'Functional/Workflow', component: WorkflowUI, args: { path: '/mock/demo.flow.py' }, parameters: { layout: 'fullscreen' } } satisfies Meta<typeof WorkflowUI>;
export default meta;
export const Editor: StoryObj<typeof meta> = {};
