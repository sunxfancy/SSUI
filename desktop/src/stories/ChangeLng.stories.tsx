import type { Meta, StoryObj } from '@storybook/react';
import ChangeLng from '../components/ChangeLng';

const meta = { title: 'Components/Language selector', component: ChangeLng } satisfies Meta<typeof ChangeLng>;
export default meta;
export const Interactive: StoryObj<typeof meta> = {};
