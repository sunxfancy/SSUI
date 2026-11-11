import React from 'react';
import { BlueprintProvider } from '@blueprintjs/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Queue from '../src/components/Queue';
import { RuntimeAdapters, RuntimeAdaptersProvider } from '../src/runtime/RuntimeAdapters';
import { QueueTask } from '../src/services/TaskService';

const waitingTask: QueueTask = {
  id: 'task-1',
  kind: 'generation',
  name: 'Runtime adapter task',
  status: 'waiting',
  progress: 0,
  createdAt: 1_700_000_000,
  error: null,
  meta: {},
};

function createRuntime(): RuntimeAdapters {
  const status = vi.fn(async () => ({ success: true, message: '运行中' }));
  return {
    executor: {
      startExecutor: status,
      stopExecutor: status,
      getExecutorStatus: status,
      restartExecutor: status,
    },
    server: {
      startServer: status,
      stopServer: status,
      getServerStatus: status,
      restartServer: status,
    },
    tasks: {
      fetchTasks: vi.fn(async () => [waitingTask]),
      removeTask: vi.fn(async () => true),
      cancelTask: vi.fn(async () => true),
      retryTask: vi.fn(async () => "retry-task"),
      clearCompleted: vi.fn(async () => {}),
      subscribe: vi.fn(() => () => {}),
    },
  };
}

function renderQueue(runtime: RuntimeAdapters) {
  return render(
    <BlueprintProvider>
      <RuntimeAdaptersProvider value={runtime}>
        <Queue />
      </RuntimeAdaptersProvider>
    </BlueprintProvider>,
  );
}

describe('Queue runtime adapter', () => {
  it('uses injected task and process adapters without a Tauri runtime', async () => {
    const runtime = createRuntime();
    renderQueue(runtime);

    expect(await screen.findByText('Runtime adapter task')).toBeVisible();
    fireEvent.click(screen.getByTitle('Cancel Task'));

    await waitFor(() => expect(runtime.tasks.cancelTask).toHaveBeenCalledWith('task-1'));
    expect(screen.getByText('Cancelled')).toBeVisible();
    expect(runtime.executor.getExecutorStatus).toHaveBeenCalled();
    expect(runtime.server.getServerStatus).toHaveBeenCalled();
  });
});
