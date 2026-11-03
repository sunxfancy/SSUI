import { test, expect, APIRequestContext } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

async function mcp(request: APIRequestContext, name: string, args = {}) {
    const response = await request.post('/test/mcp', { data: { name, arguments: args } });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
}
async function target(request: APIRequestContext, prefix: string) {
    let found: any;
    await expect.poll(async () => {
        const result = await mcp(request, 'ssui_ui_targets');
        found = result.items.find((item: any) => item.label.startsWith(prefix));
        return Boolean(found);
    }).toBeTruthy();
    return found.id as string;
}
async function command(request: APIRequestContext, target_id: string, command: string, args = {}) {
    return (await mcp(request, 'ssui_ui_call', { target_id, command, arguments: args })).result;
}

test('MCP edits real canvas layers/strokes, undo/redo, exports nonempty PNG and persists', async ({ page, request }) => {
    const files = await (await request.get('/test/files')).json();
    await page.goto('/extension/ImageExtension/canvas/?' + new URLSearchParams({ path: files.canvas }));
    await page.waitForLoadState('networkidle');
    const id = await target(request, 'Canvas:');
    await expect.poll(async () => (await command(request, id, 'canvas.snapshot')).restoring).toBe(false);
    await command(request, id, 'canvas.layer.add');
    const state = await command(request, id, 'canvas.snapshot');
    const layerId = state.activeLayer;
    expect(state.layers).toHaveLength(2);
    const { id: objectId } = await command(request, id, 'canvas.object.add', { layerId, object: { type: 'stroke', x: 0, y: 0,
        points: [{ x: 50, y: 50, pressure: 1 }, { x: 200, y: 180, pressure: 1 }], stroke: '#ff0000', strokeWidth: 30 } });
    const image = await command(request, id, 'canvas.export');
    expect(image.image).toMatch(/^data:image\/png;base64,/);
    const data = Buffer.from(image.image.split(',')[1], 'base64');
    expect(data.length).toBeGreaterThan(1000);
    mkdirSync('build/mcp-ui-evidence', { recursive: true });
    writeFileSync('build/mcp-ui-evidence/canvas-export.png', data);
    await command(request, id, 'canvas.object.update', { layerId, objectId, changes: { x: 15 } });
    expect((await command(request, id, 'canvas.snapshot')).layers[1].objects[0].x).toBe(15);
    await command(request, id, 'canvas.undo');
    expect((await command(request, id, 'canvas.snapshot')).layers[1].objects[0].x).toBe(0);
    await command(request, id, 'canvas.redo');
    expect((await command(request, id, 'canvas.snapshot')).layers[1].objects[0].x).toBe(15);
    await command(request, id, 'canvas.save');
    await page.screenshot({ path: 'build/mcp-ui-evidence/canvas.png' });
    const saved = await (await request.get('/file/text', { params: { path: files.canvas } })).json();
    expect(JSON.parse(saved.content).version).toBe(1);
});

test('MCP edits and persists the real Rete graph', async ({ page, request }) => {
    const files = await (await request.get('/test/files')).json();
    await page.goto('/functional_ui/?' + new URLSearchParams({ path: files.flow, view: 'workflow' }));
    await page.waitForLoadState('networkidle');
    const id = await target(request, 'Workflow:');
    await command(request, id, 'graph.clear');
    const node = await command(request, id, 'graph.add_node', { kind: 'input', position: { x: 50, y: 50 } });
    await command(request, id, 'graph.port', { id: node.id, action: 'add' });
    await command(request, id, 'graph.update_node', { id: node.id, label: 'Agent Input', position: { x: 100, y: 100 } });
    await command(request, id, 'graph.save');
    expect((await command(request, id, 'graph.snapshot')).nodes[0].label).toBe('Agent Input');
    await command(request, id, 'graph.fit');
    await page.screenshot({ path: 'build/mcp-ui-evidence/workflow.png' });
    await page.reload(); await page.waitForLoadState('networkidle');
    const next = await target(request, 'Workflow:');
    expect((await command(request, next, 'graph.snapshot')).nodes[0].label).toBe('Agent Input');
});

test('MCP changes Monaco buffer and preserves version/conflict checks', async ({ page, request }) => {
    const files = await (await request.get('/test/files')).json();
    await page.goto('/functional_ui/?' + new URLSearchParams({ path: files.code, view: 'code_editor' }));
    await page.waitForLoadState('networkidle');
    const id = await target(request, 'Code editor:');
    await expect.poll(async () => (await command(request, id, 'code.snapshot')).loading).toBe(false);
    const snapshot = await command(request, id, 'code.snapshot');
    await command(request, id, 'code.replace', { expectedContent: snapshot.content, content: 'print("agent")\n' });
    await command(request, id, 'code.save');
    const saved = await (await request.get('/file/text', { params: { path: files.code } })).json();
    expect(saved.content.replace(/\r\n/g, '\n')).toBe('print("agent")\n');
    const stale = await request.post('/test/mcp', { data: { name: 'ssui_ui_call', arguments: { target_id: id, command: 'code.replace', arguments: { expectedContent: snapshot.content, content: 'stale' } } } });
    expect(stale.status()).toBe(409);
});
