import type { Meta, StoryObj } from '@storybook/react';
import Queue from '../components/Queue';
import TaskService, { QueueTask } from '../services/TaskService';
import { RuntimeAdapters, RuntimeAdaptersProvider } from '../runtime/RuntimeAdapters';

const commandResult = async () => ({ success: true, message: '运行中' });
const storyRuntime: RuntimeAdapters = {
  executor: {
    startExecutor: commandResult,
    stopExecutor: commandResult,
    getExecutorStatus: commandResult,
    restartExecutor: commandResult,
  },
  server: {
    startServer: commandResult,
    stopServer: commandResult,
    getServerStatus: commandResult,
    restartServer: commandResult,
  },
  tasks: new TaskService('http://127.0.0.1:7422'),
};

const meta: Meta<typeof Queue> = {
  title: 'Components/Queue',
  component: Queue,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [Story => <RuntimeAdaptersProvider value={storyRuntime}><Story /></RuntimeAdaptersProvider>],
};

export default meta;
type Story = StoryObj<typeof Queue>;

// 生成测试数据
const generateQueueItems = (count: number) => {
  const items: QueueTask[] = [];
  const statuses: QueueTask['status'][] = ['waiting', 'processing', 'completed', 'failed', 'cancelled'];
  const types = ['安装', '更新', '卸载', '修复'];
  
  for (let i = 0; i < count; i++) {
    items.push({
      id: `item-${i}`,
      name: `测试任务 ${i + 1}`,
      kind: i % 2 === 0 ? 'download' : 'generation',
      status: statuses[i % statuses.length],
      progress: (i * 23) % 100,
      createdAt: 1760000000 - i * 3600,
      meta: {
        type: types[i % types.length],
        priority: i % 5 + 1,
      },
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

// E2E/integration story: no local items means Queue uses the injected HTTP/WebSocket task service.
export const BackendLifecycle: Story = {};

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
