import type { Model, ModelsProvider, WatchedDirectory } from '../providers/IModelsProvider';
import type { DownloadTask, IDownloaderProvider } from '../providers/IDownloaderProvider';

export const localModels: Model[] = [
    { id: 'sdxl', name: 'Demo SDXL', path: '/mock/models/demo-sdxl.safetensors', type: 'checkpoint', size: '6.5 GB', installed: false },
    { id: 'vae', name: 'Demo VAE', path: '/mock/models/demo-vae.safetensors', type: 'vae', size: '335 MB', installed: true },
];

export class MockModelsProvider implements ModelsProvider {
    constructor(private models = localModels, private failScan = false) {}
    async selectDirectory() { return '/mock/models'; }
    async scanDirectory(_path: string, onModelFound?: (model: Model) => void) {
        if (this.failScan) throw new Error('Offline scan failure');
        this.models.forEach(model => onModelFound?.({ ...model }));
        return this.models.map(model => ({ ...model }));
    }
    async addModel() { return true; }
    async getWatchedDirectories(): Promise<WatchedDirectory[]> { return []; }
    async addWatchedDirectory(path: string) { return { id: path, path }; }
    async removeWatchedDirectory() { return true; }
    async getDroppedFilePath() { return '/mock/models/demo-sdxl.safetensors'; }
}

export class MockDownloaderProvider implements IDownloaderProvider {
    async addDownloadTask(model: DownloadTask['model'], fileId?: number): Promise<DownloadTask> {
        return { id: String(model.id), model, fileId, status: 'completed', progress: 100 };
    }
    async getDownloadTasks(): Promise<DownloadTask[]> { return []; }
    async getDownloadTask(): Promise<DownloadTask | null> { return null; }
    async cancelDownloadTask() { return true; }
    async clearCompletedTasks() {}
    async getQueueStatus() { return { total: 0, pending: 0, downloading: 0, completed: 0, failed: 0 }; }
}
