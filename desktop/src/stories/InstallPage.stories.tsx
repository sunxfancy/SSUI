import { Meta, StoryObj } from '@storybook/react';
import InstallPage from '../Install';
import { MockInstallerProvider } from './MockInstallerProvider';

// 创建一个MockProvider用于故事展示
const mockProvider = new MockInstallerProvider();

const meta: Meta<typeof InstallPage> = {
  title: '安装程序/InstallPage',
  component: InstallPage,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    provider: {
      control: false,
      description: '安装提供者接口的实现',
    },
  },
};

export default meta;
type Story = StoryObj<typeof InstallPage>;

// 基本安装对话框
export const 基本安装对话框: Story = {
  args: {
    provider: mockProvider,
  },
};