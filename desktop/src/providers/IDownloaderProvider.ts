import { CivitaiModel } from '../types/civitai';

export interface DownloadTask {
    id: string;
    model: CivitaiModel;
    status: 'pending' | 'downloading' | 'completed' | 'failed';
    progress: number;
    error?: string;
}

export interface IDownloaderProvider {
    // 添加下载任务到队列
    addDownloadTask(model: CivitaiModel): Promise<DownloadTask>;
    
    // 获取所有下载任务
    getDownloadTasks(): Promise<DownloadTask[]>;
    
    // 获取特定下载任务
    getDownloadTask(taskId: string): Promise<DownloadTask | null>;
    
    // 取消下载任务
    cancelDownloadTask(taskId: string): Promise<boolean>;
    
    // 清除已完成的下载任务
    clearCompletedTasks(): Promise<void>;
    
    // 获取下载队列状态
    getQueueStatus(): Promise<{
        total: number;
        pending: number;
        downloading: number;
        completed: number;
        failed: number;
    }>;
}