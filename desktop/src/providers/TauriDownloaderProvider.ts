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

    private taskUrls = new Map<string, string>();
    private disposed = false;
    private ready: Promise<void>;

    constructor(private onChange?: () => void) {
        this.ready = this.initializeEventListeners().then(() => this.loadTasks());
        void this.ready.catch(error => console.error('初始化下载器失败:', error));
    }

    private async initializeEventListeners() {
        const register = async (name: string, callback: (payload: any) => void) => {
            const unlisten = await listen(name, event => {
                if (!this.disposed) { callback(event.payload); this.onChange?.(); }
            });
            if (this.disposed) unlisten();
            else this.eventUnlisteners.push(unlisten);
        };
        const find = (url: string) => {
            const id = Array.from(this.taskUrls).find(([, value]) => value === url)?.[0];
            return id ? this.tasks.get(id) : undefined;
        };
        await register('download-progress', ({ url, progress, total }) => {
            const task = find(url);
            if (task && total > 0) { task.progress = Math.round(progress / total * 100); task.status = 'downloading'; }
        });
        await register('download-completed', url => {
            const task = find(url); if (task) { task.status = 'completed'; task.progress = 100; }
        });
        await register('download-failed', ({ url, error }) => {
            const task = find(url); if (task) { task.status = 'failed'; task.error = error; }
        });
        await register('download-cancelled', url => {
            const task = find(url); if (task) { task.status = 'failed'; task.error = '下载已取消'; }
        });
    }

    private async loadTasks() {
        try {
            const tasks = await invoke<RustDownloadTask[]>('get_download_task_list');
            if (this.disposed) return;
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

                this.taskUrls.set(task.url, task.url);
                this.tasks.set(task.url, {
                    id: task.url,
                    model,
                    status: this.mapTaskStatus(task.status),
                    progress: task.total_blocks > 0 ? Math.round(task.progress / task.total_blocks * 100) : 0,
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

    async addDownloadTask(model: CivitaiModel, fileId?: number): Promise<DownloadTask> {
        const taskId = model.id.toString();
        const task: DownloadTask = {
            id: taskId,
            model,
            fileId,
            status: 'pending',
            progress: 0
        };

        const rootState = GlobalStateManager.getInstance().getRootState();
        const rootPath = rootState?.path;

        try {
            await this.ready;
            if (this.disposed) throw new Error('下载器已关闭');
            if (!rootPath) throw new Error('未找到安装路径');
            // 获取模型下载URL
            const latestVersion = model.modelVersions[0];
            if (!latestVersion) {
                throw new Error('无法获取模型版本信息');
            }

            let downloadUrl: string;
            let fileName: string;
            let file = undefined;
            if (fileId) {
                file = latestVersion.files.find(f => f.id === fileId);
                if (!file) {
                    throw new Error('无法找到指定的文件');
                }
            } else {
                file = latestVersion.files[0];
            }
            
            if (!file) throw new Error('没有可下载的文件');
            const address = new URL(file.downloadUrl);
            for (const [key, value] of Object.entries(file.metadata)) {
                if (value) address.searchParams.set(key, value);
            }
            downloadUrl = address.toString();
            fileName = file.name;

            console.log("找到了要下载的文件metadata: ", downloadUrl, fileName);
           

            // Register before IPC resolves: progress/completion events may arrive first.
            this.tasks.set(taskId, task);
            this.taskUrls.set(taskId, downloadUrl);
            task.status = 'downloading';
            // 创建下载任务
            await invoke('create_download_task', {
                url: downloadUrl,
                output_path: `${rootPath}/resources/civitai_models/${model.type}/${fileName}`,
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
        await this.ready;
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
                url: this.taskUrls.get(taskId)
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
            this.taskUrls.delete(id);
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
        this.disposed = true;
        this.eventUnlisteners.splice(0).forEach(unlisten => unlisten());
    }
} 