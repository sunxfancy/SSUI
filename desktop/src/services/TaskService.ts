import GlobalStateManager from './GlobalState';

export interface QueueTask {
    id: string;
    kind: 'download' | 'generation';
    name: string;
    status: 'waiting' | 'processing' | 'completed' | 'failed' | 'cancelled';
    progress: number;
    createdAt: number;
    error?: string | null;
    meta?: Record<string, any>;
}

/**
 * 任务队列服务：封装 /api/tasks 的 REST 接口与 websocket task_update 订阅。
 */
class TaskService {
    private static instance: TaskService | null = null;
    private ws: WebSocket | null = null;
    private listeners: ((task: QueueTask) => void)[] = [];

    public static getInstance(): TaskService {
        if (!TaskService.instance) {
            TaskService.instance = new TaskService();
        }
        return TaskService.instance;
    }

    private getBaseUrl(): string {
        const rootState = GlobalStateManager.getInstance().getRootState();
        const host = rootState?.host || 'localhost';
        const port = rootState?.port || 7422;
        return `http://${host}:${port}`;
    }

    public async fetchTasks(): Promise<QueueTask[]> {
        const response = await fetch(`${this.getBaseUrl()}/api/tasks`);
        if (!response.ok) {
            throw new Error(`Failed to fetch tasks: ${response.status}`);
        }
        const data = await response.json();
        return data.items || [];
    }

    public async removeTask(id: string): Promise<boolean> {
        const response = await fetch(`${this.getBaseUrl()}/api/tasks/${encodeURIComponent(id)}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        return data.success === true;
    }

    public async cancelTask(id: string): Promise<boolean> {
        const response = await fetch(`${this.getBaseUrl()}/api/tasks/${encodeURIComponent(id)}/cancel`, {
            method: 'POST'
        });
        const data = await response.json();
        return data.success === true;
    }

    public async clearCompleted(): Promise<void> {
        await fetch(`${this.getBaseUrl()}/api/tasks/clear`, {
            method: 'POST'
        });
    }

    /**
     * 通过统一任务队列创建下载任务（HTTP 直链或 HuggingFace 仓库）。
     * @returns 任务 id；失败抛异常。
     */
    public async createDownloadTask(
        kind: string,
        name: string,
        url?: string,
        repo_id?: string
    ): Promise<string> {
        const response = await fetch(`${this.getBaseUrl()}/api/tasks/download`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ kind, name, url, repo_id })
        });
        if (!response.ok) {
            throw new Error(`Failed to create download task: ${response.status}`);
        }
        const data = await response.json();
        if (!data.task_id) {
            throw new Error('Failed to create download task: missing task_id');
        }
        return data.task_id as string;
    }

    public subscribe(callback: (task: QueueTask) => void): () => void {
        this.listeners.push(callback);
        this.ensureSocket();
        return () => {
            this.listeners = this.listeners.filter(listener => listener !== callback);
        };
    }

    private ensureSocket(): void {
        if (this.ws) return;
        const wsUrl = this.getBaseUrl().replace(/^http/, 'ws') + '/ws';
        const socket = new WebSocket(wsUrl);
        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'task_update' && data.task) {
                    this.listeners.forEach(listener => listener(data.task as QueueTask));
                }
            } catch (error) {
                console.error('解析任务推送失败:', error);
            }
        };
        socket.onclose = () => {
            this.ws = null;
        };
        this.ws = socket;
    }
}

export default TaskService;
