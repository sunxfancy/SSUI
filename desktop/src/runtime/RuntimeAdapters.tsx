import React, { createContext, useContext } from 'react';
import { IExecutorProvider } from '../providers/IExecutorProvider';
import { IServerProvider } from '../providers/IServerProvider';
import ExecutorService from '../services/Executor';
import ServerService from '../services/Server';
import TaskService, { QueueTask } from '../services/TaskService';

export interface TaskClient {
  fetchTasks(): Promise<QueueTask[]>;
  removeTask(id: string): Promise<boolean>;
  cancelTask(id: string): Promise<boolean>;
  clearCompleted(): Promise<void>;
  subscribe(callback: (task: QueueTask) => void): () => void;
}

export interface RuntimeAdapters {
  executor: IExecutorProvider;
  server: IServerProvider;
  tasks: TaskClient;
}

const RuntimeContext = createContext<RuntimeAdapters | null>(null);
let productionAdapters: RuntimeAdapters | null = null;

function getProductionAdapters(): RuntimeAdapters {
  if (!productionAdapters) {
    productionAdapters = {
      executor: ExecutorService.getInstance(),
      server: ServerService.getInstance(),
      tasks: TaskService.getInstance(),
    };
  }
  return productionAdapters;
}

export const RuntimeAdaptersProvider: React.FC<{
  value: RuntimeAdapters;
  children: React.ReactNode;
}> = ({ value, children }) => (
  <RuntimeContext.Provider value={value}>{children}</RuntimeContext.Provider>
);

export function useRuntimeAdapters(): RuntimeAdapters {
  return useContext(RuntimeContext) ?? getProductionAdapters();
}
