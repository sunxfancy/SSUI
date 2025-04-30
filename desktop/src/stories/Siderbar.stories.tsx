import type { Meta, StoryObj } from '@storybook/react';
import { WorkSpace } from '../components/WorkSpace';
import { MockFilesystemProvider } from './MockFilesystemProvider';

// 创建 Mock 文件系统提供程序的实例

const meta: Meta<typeof WorkSpace> = {
  component: WorkSpace,
  parameters: {
    layout: 'fullscreen'
  }
};

export default meta;
type Story = StoryObj<typeof WorkSpace>;

export const Primary: Story = {
  args: {
    filesystemProvider: new MockFilesystemProvider(),
    currentWorkspace: "/"
  }
};

