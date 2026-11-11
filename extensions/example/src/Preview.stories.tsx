import type { Meta, StoryObj } from '@storybook/react';
import { ImagePreview2 } from './main';
import { sampleImage } from '../../../.storybook/mocks/fixtures';
const meta = { title: 'Extensions/Example/Image preview', component: ImagePreview2, args: { src: sampleImage } } satisfies Meta<typeof ImagePreview2>;
export default meta;
export const Image: StoryObj<typeof meta> = {};
export const Empty: StoryObj<typeof meta> = { args: { src: '' } };
