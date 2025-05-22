import { invoke } from '@tauri-apps/api/core';
import { IDownloaderProvider, DownloadTask } from './IDownloaderProvider';
import { CivitaiModel } from '../types/civitai';
import { listen } from '@tauri-apps/api/event';
import GlobalStateManager from '../services/GlobalState';

interface RustDownloadTask {
    url: string;
    output_path: string;
    sha256: string;
    progress: number;
    total_blocks: number;
    status: 'Pending' | 'Downloading' | 'Paused' | 'Completed' | 'Failed' | 'Cancelled';
}

export class TauriDownloaderProvider implements IDownloaderProvider {
    private tasks: Map<string, DownloadTask> = new Map();
    private eventUnlisteners: (() => void)[] = [];

    constructor() {
        this.initializeEventListeners();
        this.loadTasks();
    }

    private async initializeEventListeners() {
        // 监听下载进度事件
        const progressUnlisten = await listen('download-progress', (event) => {
            const { url, progress, total } = event.payload as any;
            const task = Array.from(this.tasks.values()).find(t => t.model.id.toString() === url);
            if (task) {
                task.progress = Math.round((progress / total) * 100);
            }
        });

        // 监听下载完成事件
        const completedUnlisten = await listen('download-completed', (event) => {
            const url = event.payload as string;
            const task = Array.from(this.tasks.values()).find(t => t.model.id.toString() === url);
            if (task) {
                task.status = 'completed';
                task.progress = 100;
            }
        });

        // 监听下载失败事件
        const failedUnlisten = await listen('download-failed', (event) => {
            const { url, error } = event.payload as any;
            const task = Array.from(this.tasks.values()).find(t => t.model.id.toString() === url);
            if (task) {
                task.status = 'failed';
                task.error = error;
            }
        });

        this.eventUnlisteners.push(
            progressUnlisten,
            completedUnlisten,
            failedUnlisten
        );
    }

    private async loadTasks() {
        try {
            const tasks = await invoke<RustDownloadTask[]>('get_download_task_list');
            tasks.forEach(task => {
                const model: CivitaiModel = {
                    id: parseInt(task.url) || 0,
                    name: task.output_path.split('/').pop() || '',
                    type: 'unknown',
                    description: '',
                    nsfw: false,
                    tags: [],
                    stats: {
                        downloadCount: 0,
                        ratingCount: 0,
                        rating: 0,
                        commentCount: 0,
                        thumbsUpCount: 0
                    },
                    metadata: {
                        totalItems: 0,
                        currentPage: 1,
                        pageSize: 10,
                        totalPages: 1
                    },
                    modelVersions: [{
                        id: parseInt(task.url) || 0,
                        name: '',
                        description: '',
                        createdAt: '',
                        downloadUrl: task.url,
                        trainedWords: [],
                        files: [],
                        images: []
                    }]
                };

                this.tasks.set(task.url, {
                    id: task.url,
                    model,
                    status: this.mapTaskStatus(task.status),
                    progress: task.progress,
                    error: task.status === 'Failed' ? '下载失败' : undefined
                });
            });
        } catch (error) {
            console.error('加载下载任务失败:', error);
        }
    }

    private mapTaskStatus(status: RustDownloadTask['status']): 'pending' | 'downloading' | 'completed' | 'failed' {
        switch (status) {
            case 'Pending':
                return 'pending';
            case 'Downloading':
                return 'downloading';
            case 'Completed':
                return 'completed';
            case 'Failed':
            case 'Cancelled':
                return 'failed';
            default:
                return 'pending';
        }
    }

    async addDownloadTask(model: CivitaiModel): Promise<DownloadTask> {
        const taskId = model.id.toString();
        const task: DownloadTask = {
            id: taskId,
            model,
            status: 'pending',
            progress: 0
        };

        const rootState = GlobalStateManager.getInstance().getRootState();
        const rootPath = rootState?.path;

        try {
            // 获取模型下载URL
            const downloadUrl = model.modelVersions[0]?.downloadUrl;
            if (!downloadUrl) {
                throw new Error('无法获取模型下载地址');
            }

            // 创建下载任务
            await invoke('create_download_task', {
                url: downloadUrl,
                output_path: `${rootPath}/resources/civitai_models/${model.type}/${model.name}.safetensors`,
                sha256: '' // 暂时不验证SHA256
            });

            this.tasks.set(taskId, task);
            return task;
        } catch (error) {
            task.status = 'failed';
            task.error = error instanceof Error ? error.message : '未知错误';
            this.tasks.set(taskId, task);
            throw error;
        }
    }

    async getDownloadTasks(): Promise<DownloadTask[]> {
        return Array.from(this.tasks.values());
    }

    async getDownloadTask(taskId: string): Promise<DownloadTask | null> {
        return this.tasks.get(taskId) || null;
    }

    async cancelDownloadTask(taskId: string): Promise<boolean> {
        const task = this.tasks.get(taskId);
        if (!task) {
            return false;
        }

        try {
            await invoke('cancel_download_task', {
                url: task.model.id.toString()
            });
            task.status = 'failed';
            task.error = '下载已取消';
            return true;
        } catch (error) {
            console.error('取消下载失败:', error);
            return false;
        }
    }

    async clearCompletedTasks(): Promise<void> {
        const completedTasks = Array.from(this.tasks.entries())
            .filter(([_, task]) => task.status === 'completed' || task.status === 'failed');

        for (const [id, _] of completedTasks) {
            this.tasks.delete(id);
        }
    }

    async getQueueStatus(): Promise<{
        total: number;
        pending: number;
        downloading: number;
        completed: number;
        failed: number;
    }> {
        const tasks = Array.from(this.tasks.values());
        return {
            total: tasks.length,
            pending: tasks.filter(t => t.status === 'pending').length,
            downloading: tasks.filter(t => t.status === 'downloading').length,
            completed: tasks.filter(t => t.status === 'completed').length,
            failed: tasks.filter(t => t.status === 'failed').length
        };
    }

    // 清理事件监听器
    destroy() {
        this.eventUnlisteners.forEach(unlisten => unlisten());
    }
} 