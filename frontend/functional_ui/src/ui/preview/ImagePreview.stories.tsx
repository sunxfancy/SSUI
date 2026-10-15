import type { Meta, StoryObj } from '@storybook/react';
import { ImagePreview } from './ImagePreview';
import { sampleImage } from '../../../../../.storybook/mocks/fixtures';
const meta = {
    title: 'Functional/Image preview', component: ImagePreview,
    args: { path: '/mock/preview.svg', resolveImageUrl: () => sampleImage },
} satisfies Meta<typeof ImagePreview>;
export default meta;
export const Image: StoryObj<typeof meta> = {};
