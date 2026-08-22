import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Navbar } from '../components/Navbar';

const NavbarWrapper = ({ initialNavIndex = 0 }: { initialNavIndex?: number }) => {
  const [navIndex, setNavIndex] = useState(initialNavIndex);

  return (
    <div style={{ height: '100vh', display: 'flex' }}>
      <Navbar
        navIndex={navIndex}
        updateNavIndex={setNavIndex}
        openSettings={() => console.log('打开设置')}
      />
    </div>
  );
};

const meta: Meta<typeof NavbarWrapper> = {
  title: 'Components/Navbar',
  component: NavbarWrapper,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof NavbarWrapper>;

export const Default: Story = {
  args: {
    initialNavIndex: 0,
  },
};

export const 模型管理选中: Story = {
  args: {
    initialNavIndex: 1,
  },
};

export const 队列选中: Story = {
  args: {
    initialNavIndex: 2,
  },
};

export const 扩展选中: Story = {
  args: {
    initialNavIndex: 3,
  },
};
