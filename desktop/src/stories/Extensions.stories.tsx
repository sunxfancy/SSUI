import type { Meta, StoryObj } from '@storybook/react';
import { Extensions } from '../components/Extensions';
import { MockExtensionsProvider } from './MockExtensionsProvider';

const meta: Meta<typeof Extensions> = {
  title: 'Components/Extensions',
  component: Extensions,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Extensions>;

export const Default: Story = {
  args: {
    provider: new MockExtensionsProvider(),
    onOpenExtensionStore: () => console.log('打开扩展商城'),
  },
};

export const WithSearch: Story = {
  args: {
    provider: new MockExtensionsProvider(),
    onOpenExtensionStore: () => console.log('打开扩展商城'),
  },
  play: async ({ canvasElement }) => {
    const searchInput = canvasElement.querySelector('input');
    if (searchInput) {
      searchInput.value = '数据';
      searchInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  },
};

export const EmptySearch: Story = {
  args: {
    provider: new MockExtensionsProvider(),
    onOpenExtensionStore: () => console.log('打开扩展商城'),
  },
  play: async ({ canvasElement }) => {
    const searchInput = canvasElement.querySelector('input');
    if (searchInput) {
      searchInput.value = '不存在的扩展';
      searchInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  },
};
