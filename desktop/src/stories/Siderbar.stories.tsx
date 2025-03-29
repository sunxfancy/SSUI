import type { Meta, StoryObj } from '@storybook/react';
import { Sidebar } from '../components/Sidebar';
import { MockFilesystemProvider } from './MockFilesystemProvider';

// 创建 Mock 文件系统提供程序的实例

const meta: Meta<typeof Sidebar> = {
  component: Sidebar,
  parameters: {
    layout: 'fullscreen'
  }
};

export default meta;
type Story = StoryObj<typeof Sidebar>;

export const Primary: Story = {
  args: {
    filesystemProvider: new MockFilesystemProvider(),
    currentWorkspace: "/"
  }
};

