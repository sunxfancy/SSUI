export const sampleImage = 'data:image/svg+xml,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="512" height="512" fill="#304e73"/><circle cx="256" cy="256" r="150" fill="#64c4ba"/></svg>');

export const defaultRoutes = {
    'GET /api/available_models': [
        { name: 'Demo SDXL', path: '/mock/models/demo.safetensors', type: 'checkpoint', base_model: 'SDXL', tags: ['offline'] },
    ],
    'GET /api/script': { root_path: '/mock', functions: { preview: { params: { prompt: 'builtins.str', seed: 'builtins.int' }, returns: ['builtins.str'] } } },
    'POST /api/prepare': {},
    'POST /api/execute': ['Offline preview completed'],
    'GET /api/flow/operators': { operators: [] },
    'GET /api/tasks': { items: [] },
    'GET /files/image': [],
    'GET /files/script': ['/mock/drawing.py'],
    'POST /files/upload': { path: sampleImage },
    'GET /config/': { ui: {} },
    'POST /config/': {},
};
