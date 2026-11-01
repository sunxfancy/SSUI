import { sampleImage } from './fixtures';

export const modelRoutes = {
    'GET /api/preset_models': { items: [{
        id: 'demo-sdxl', name: 'Demo SDXL Bundle', type: 'checkpoint', base: 'SDXL', source: 'demo/sdxl',
        description: 'Offline model bundle', imageUrl: sampleImage, size: '6.5 GB',
        models: [{ name: 'Demo SDXL', source: 'demo/sdxl' }, { name: 'Demo VAE', source: 'demo/vae' }],
    }] },
    'GET /api/civitai/models': { items: [{
        id: 1, name: 'Demo Civitai SDXL', type: 'Checkpoint', description: 'Offline example', nsfw: false, tags: ['SDXL'],
        stats: { downloadCount: 1200, thumbsUpCount: 32, commentCount: 4, ratingCount: 10, rating: 5 },
        modelVersions: [{ id: 1, name: 'v1', description: '', createdAt: '2026-01-01', trainedWords: [],
            downloadUrl: '/mock/model', files: [{ id: 1, name: 'demo.safetensors', sizeKB: 1024, type: 'Model', metadata: { format: 'SafeTensor' }, downloadUrl: '/mock/model' }],
            images: [{ url: sampleImage, nsfw: false, width: 512, height: 512, hash: '', meta: {} }],
        }], metadata: { totalItems: 1, currentPage: 1, pageSize: 100, totalPages: 1 },
    }] },
    'GET /api/hf/models': [{ id: 'demo/sdxl', modelId: 'demo/sdxl', author: 'demo', private: false,
        downloads: 1200, likes: 32, tags: ['SDXL'], pipeline_tag: 'text-to-image', lastModified: '2026-01-01' }],
    'GET /api/hf/models/demo%2Fsdxl': { id: 'demo/sdxl', author: 'demo', tags: ['SDXL'], downloads: 1200, likes: 32 },
    'POST /api/tasks/download': () => ({ task_id: `offline-${crypto.randomUUID()}` }),
};
