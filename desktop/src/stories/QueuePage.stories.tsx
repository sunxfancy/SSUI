import type { Meta, StoryObj } from '@storybook/react';
import Queue from '../components/Queue';

const meta: Meta<typeof Queue> = {
  title: 'Components/Queue',
  component: Queue,
  parameters: {
    layout: 'fullscreen',
  },
};

export default meta;
type Story = StoryObj<typeof Queue>;

// 生成测试数据
const generateQueueItems = (count: number) => {
  const items = [];
  const statuses: ('waiting' | 'processing' | 'completed' | 'failed')[] = ['waiting', 'processing', 'completed', 'failed'];
  const types = ['安装', '更新', '卸载', '修复'];
  
  for (let i = 0; i < count; i++) {
    items.push({
      id: `item-${i}`,
      name: `测试任务 ${i + 1}`,
      status: statuses[i % statuses.length],
      progress: Math.floor(Math.random() * 100),
      createdAt: new Date(Date.now() - Math.random() * 10000000000),
      type: types[i % types.length],
      priority: Math.floor(Math.random() * 5) + 1,
    });
  }
  return items;
};

// 空队列
export const Empty: Story = {
  args: {
    items: [],
  },
};

// 少量任务
export const FewItems: Story = {
  args: {
    items: generateQueueItems(3),
  },
};

// 大量任务
export const ManyItems: Story = {
  args: {
    items: generateQueueItems(20),
  },
};

// 带事件处理的示例
export const WithEventHandlers: Story = {
  args: {
    items: generateQueueItems(5),
    onRemoveItem: (id) => console.log('移除任务:', id),
    onPauseItem: (id) => console.log('暂停任务:', id),
    onResumeItem: (id) => console.log('继续任务:', id),
  },
};
