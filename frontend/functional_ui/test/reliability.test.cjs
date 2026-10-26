const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
// Request/state regression tests; no DOM or Monaco rendering is simulated.
function load(file, name, globals = {}) {
  class Component {
    constructor(props) { this.props = props; }
    setState(patch) { Object.assign(this.state, typeof patch === 'function' ? patch(this.state) : patch); }
  }
  const react = { Component, createRef: () => ({ current: null }) };
  const ctx = { exports: {}, console, URLSearchParams, self: {}, Date, AbortController, DOMException, ...globals,
    fetch: (...args) => ctx.request(...args),
    require: id => id === 'react' ? { ...react, default: react } : {} };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(`${__dirname}/../src/ui/${file}.tsx`, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX }
  }).outputText, ctx);
  return { Type: ctx.exports[name], ctx };
}
function deferred() { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; }
const response = data => ({ ok: true, json: async () => data });
test('save guards loading/errors, suppresses duplicates and preserves newer edits', async () => {
  const { Type, ctx } = load('code_editor/CodeEditor', 'CodeEditor');
  const ui = new Type({ path: 'a.py' });
  let value = 'first', calls = 0;
  ui.editor = { getValue: () => value };
  ui.version = 'initial-version';
  const pending = deferred(); ctx.request = () => { calls++; return pending.promise; };
  await ui.handleSave(); assert.equal(calls, 0);
  ui.state.loading = false; ui.state.loadError = new Error('failed');
  await ui.handleSave(); assert.equal(calls, 0);
  ui.state.loadError = null;
  const saving = ui.handleSave(); await ui.handleSave(); assert.equal(calls, 1);
  value = 'new edits'; pending.resolve(response({ success: true, version: 'saved-version' })); await saving;
  assert.equal(ui.state.dirty, true); assert.equal(ui.state.saving, false);
});
test('run suppresses duplicates and exposes business errors', async () => {
  const { Type, ctx } = load('functional/FunctionalUI', 'FunctionalUI');
  const ui = new Type({ path: 'a.py' });
  Object.assign(ui.state, { loading: false, functions: { main: { params: {}, returns: [] } } });
  const pending = deferred(); let calls = 0;
  ctx.request = () => { calls++; return pending.promise; };
  const running = ui.handleRun(); await ui.handleRun();
  ui.handleSelectFunc({ name: 'other' });
  assert.equal(ui.state.selectedFunc, undefined); assert.equal(calls, 1);
  pending.resolve(response({ error: 'executor unavailable' })); await running;
  assert.equal(ui.state.runError, 'executor unavailable'); assert.equal(ui.state.running, false);
});
test('run maps output keys and rejects malformed results', async () => {
  const { Type, ctx } = load('functional/FunctionalUI', 'FunctionalUI');
  const ui = new Type({ path: 'a.py' });
  Object.assign(ui.state, { loading: false, functions: { main: { params: {}, returns: ['str'] } } });
  let output; ui.refOutputs.set('0', { current: { onUpdate: v => output = v } });
  ctx.request = async () => response(['hello']); await ui.handleRun(); assert.equal(output, 'hello');
  ctx.request = async () => response({ unexpected: true }); await ui.handleRun();
  assert.match(ui.state.runError, /Invalid execution response/);
});
test('late details cannot overwrite newer selection', async () => {
  const { Type, ctx } = load('functional/Details', 'DetailsPanel');
  const ui = new Type({ path: 'a.py', selected: 'a' });
  const pending = deferred(); ctx.request = () => pending.promise;
  const first = ui.fetchDetails(); ui.props = { path: 'a.py', selected: 'b' };
  ctx.request = async () => response({ newer: {} }); await ui.fetchDetails();
  pending.resolve(response({ older: {} })); await first;
  assert.ok(ui.state.details.newer); assert.equal(ui.state.details.older, undefined);
});

test('image paths round trip special characters and stale callbacks are ignored', () => {
  const images = [];
  class FakeImage { constructor() { images.push(this); } }
  const { Type } = load('preview/ImagePreview', 'ImagePreview', { Image: FakeImage });
  const ui = new Type({ path: '图片 & #1.png' });
  ui.loadImage();
  assert.equal(new URL(images[0].src, 'http://localhost').searchParams.get('path'), '图片 & #1.png');
  const oldFailure = images[0].onerror;
  ui.state.imagePath = 'second.png'; ui.loadImage();
  assert.equal(images[0].onerror, null);
  images[1].onload(); oldFailure();
  assert.equal(ui.state.error, null); assert.equal(ui.state.loading, false);
  ui.componentWillUnmount(); assert.equal(images[1].onload, null);
});

test('save conflict preserves local edits and sends the loaded version', async () => {
  const { Type, ctx } = load('code_editor/CodeEditor', 'CodeEditor');
  const ui = new Type({ path: 'a.py' });
  ui.editor = { getValue: () => 'local edits' };
  ui.version = 'original-version';
  Object.assign(ui.state, { loading: false, dirty: true });
  let payload;
  ctx.request = async (_url, options) => {
    payload = JSON.parse(options.body);
    return { ok: false, status: 409, json: async () => ({ detail: 'changed' }) };
  };
  await ui.handleSave();
  assert.equal(payload.expected_version, 'original-version');
  assert.equal(ui.version, 'original-version');
  assert.equal(ui.state.dirty, true);
  assert.equal(ui.editor.getValue(), 'local edits');
  assert.ok(ui.state.saveError);
  assert.equal(ui.state.savedAt, null);
});

test('loading a missing file never enables saving an empty replacement', async () => {
  const { Type, ctx } = load('code_editor/CodeEditor', 'CodeEditor');
  const ui = new Type({ path: 'missing.py' });
  let calls = 0;
  ui.editor = { getValue: () => '', updateOptions: () => {} };
  ctx.request = async () => { calls++; return { ok: false, status: 404 }; };
  await ui.loadContent(); await ui.handleSave();
  assert.equal(calls, 1);
  assert.ok(ui.state.loadError);
  assert.equal(ui.version, null);
});
