const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function modules(globals = {}) {
    const cache = new Map();
    function load(name) {
        if (cache.has(name)) return cache.get(name);
        const context = { exports: {}, setTimeout, clearTimeout, AbortController, ...globals,
            require: relative => load(path.basename(relative)) };
        vm.runInNewContext(ts.transpileModule(fs.readFileSync(`${__dirname}/../src/config/${name}.ts`, 'utf8'), {
            compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
        }).outputText, context);
        cache.set(name, context.exports);
        return context.exports;
    }
    return load;
}
const deferred = () => { let resolve; let reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const tick = () => new Promise(resolve => setImmediate(resolve));
const defaults = { theme: 'system', auto_open_details: true, external_code_editor: '', civitai_token: '' };

test('load cannot erase edits; no write starts before loading completes', async () => {
    const { ConfigStore } = modules()('configStore');
    const loading = deferred(); const patches = [];
    const store = new ConfigStore({ load: () => loading.promise, save: async patch => {
        patches.push(patch); return { ...defaults, ...patch };
    } });
    store.update({ theme: 'dark' });
    const saved = store.save(); await tick(); assert.equal(patches.length, 0);
    loading.resolve({ ...defaults, external_code_editor: 'server-editor' });
    await saved;
    assert.equal(patches[0].theme, 'dark');
    assert.equal(store.getSnapshot().config.theme, 'dark');
    assert.equal(store.getSnapshot().saveStatus, 'saved');
});

test('writes are serial and older save responses preserve optimistic edits', async () => {
    const { ConfigStore } = modules()('configStore');
    const requests = [];
    const store = new ConfigStore({ load: async () => defaults, save: patch => {
        const pending = deferred(); requests.push({ patch, ...pending }); return pending.promise;
    } });
    await store.load(); store.update({ theme: 'dark' }); const save = store.save();
    await tick(); store.update({ theme: 'light', auto_open_details: false });
    assert.equal(store.save(), save); assert.equal(requests.length, 1);
    requests[0].resolve({ ...defaults, theme: 'dark' }); await tick();
    assert.equal(requests.length, 2);
    assert.equal(store.getSnapshot().config.theme, 'light');
    assert.notEqual(store.getSnapshot().saveStatus, 'saved');
    requests[1].resolve({ ...defaults, theme: 'light', auto_open_details: false }); await save;
    assert.equal(store.getSnapshot().saveStatus, 'saved');
});

test('failed saves retain newer fields and manual retry persists them', async () => {
    const { ConfigStore } = modules()('configStore');
    const pending = deferred(); let patch;
    const service = { load: async () => defaults, save: () => pending.promise };
    const store = new ConfigStore(service);
    await store.load(); store.update({ theme: 'dark', external_code_editor: 'editor' });
    const save = store.save(); await tick(); store.update({ theme: 'light' });
    pending.reject(new Error('offline')); await save;
    assert.equal(store.getSnapshot().saveStatus, 'error');
    assert.match(store.getSnapshot().saveError, /offline/);
    service.save = async value => { patch = value; return { ...defaults, ...value }; };
    await store.save();
    assert.equal(patch.theme, 'light'); assert.equal(patch.external_code_editor, 'editor');
    assert.equal(store.getSnapshot().saveError, null);
});

test('malformed cache and server fields cannot poison configuration', async () => {
    const load = modules({ localStorage: { getItem: () => '{invalid', setItem: () => { throw new Error('quota'); } } });
    const { ConfigService, validateUiConfig } = load('configService');
    assert.equal(Object.keys(validateUiConfig(['dark'])).length, 0);
    const service = new ConfigService({ get: async () => ({ ui: { theme: 'invalid', auto_open_details: 'false', external_code_editor: 'code', unknown: true } }), post: async () => ({ message: 'Config updated' }) });
    const config = await service.load();
    assert.equal(config.theme, 'system'); assert.equal(config.auto_open_details, true);
    assert.equal(config.external_code_editor, 'code'); assert.equal(config.unknown, undefined);
    const saved = await service.save({ theme: 'light' });
    assert.equal(saved.external_code_editor, 'code'); assert.equal(saved.theme, 'light');
});

test('config HTTP errors fail saves and requests use same-origin URLs', async () => {
    const urls = [];
    const { ConfigService } = modules({ localStorage: { getItem: () => null, setItem: () => {} },
        fetch: async url => { urls.push(url); return { ok: false, status: 503 }; } })('configService');
    const service = new ConfigService();
    assert.equal((await service.load()).theme, 'system');
    await assert.rejects(service.save({ theme: 'dark' }), /503/);
    assert.deepEqual(urls, ['/config/', '/config/']);
});
