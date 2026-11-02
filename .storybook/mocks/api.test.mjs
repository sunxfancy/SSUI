import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createOfflineApi } from './api.mjs';

test('relative and absolute API requests use method-specific fixtures without network', async () => {
    const api = createOfflineApi(() => assert.fail('network escaped'), 'http://localhost:6006');
    api.configure({ routes: { 'GET /api/models': ({ url }) => [url.searchParams.get('q')], 'POST /api/models': { saved: true } } });
    assert.deepEqual(await (await api.fetch('/api/models?q=demo')).json(), ['demo']);
    assert.deepEqual(await (await api.fetch('http://localhost:7422/api/models', { method: 'POST' })).json(), { saved: true });
    await assert.rejects(api.fetch('/api/missing'), /Missing mock/);
    await assert.rejects(api.fetch('https://example.com/service'), /Missing mock/);
});
test('scenario replacement resets routes; HTTP errors are preserved', async () => {
    const api = createOfflineApi(() => assert.fail('network escaped'), 'http://localhost:6006');
    api.configure({ routes: { 'GET /api/example': () => new Response('failure', { status: 503 }) } });
    assert.equal((await api.fetch('/api/example')).status, 503);
    api.configure();
    await assert.rejects(api.fetch('/api/example'), /Missing mock/);
});
test('delayed requests honor abort and asset requests pass through', async () => {
    let assets = 0;
    const api = createOfflineApi(async () => { assets++; return new Response('asset'); }, 'http://localhost:6006');
    api.configure({ delay: 1000, routes: { 'GET /api/example': {} } });
    const controller = new AbortController();
    const request = api.fetch(new Request('http://localhost:6006/api/example', { signal: controller.signal }));
    controller.abort();
    await assert.rejects(request, { name: 'AbortError' });
    await api.fetch('/src/preview.tsx');
    await api.fetch('data:image/svg+xml,test');
    assert.equal(assets, 2);
});
