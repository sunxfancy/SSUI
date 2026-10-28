const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { resolveConfig, executable } = require('./dev_config.cjs');
function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssui-config-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

test('retopology settings preserve WSL paths and environment overrides', t => {
  const repo = fixture(t);
  fs.writeFileSync(path.join(repo, '.ssui-dev.json'), JSON.stringify({
    SSUI_P3SAM_PYTHON: '/home/user/p3sam/bin/python', SSUI_P3SAM_WSL_DISTRO: 'Ubuntu',
    SSUI_P3SAM_DEVICE: 'cpu', SSUI_QUADRIFLOW_EXECUTABLE: '/opt/quadriflow',
  }));
  const config = resolveConfig({SSUI_P3SAM_DEVICE: 'cuda'}, repo, path.join(repo, 'home'));
  assert.equal(config.SSUI_P3SAM_PYTHON, '/home/user/p3sam/bin/python');
  assert.equal(config.SSUI_P3SAM_WSL_DISTRO, 'Ubuntu');
  assert.equal(config.SSUI_P3SAM_DEVICE, 'cuda');
  assert.equal(config.SSUI_QUADRIFLOW_EXECUTABLE, '/opt/quadriflow');
});
test('unconfigured checkout keeps its own venv', t => {
  const repo = fixture(t);
  assert.equal(resolveConfig({}, repo, path.join(repo, 'empty-home')).SSUI_VENV_PATH, path.join(repo, '.venv'));
});
test('two worktrees share configurable resources while source imports stay isolated', t => {
  const dir = fixture(t);
  const configPath = path.join(dir, 'machine.json');
  fs.writeFileSync(configPath, JSON.stringify({SSUI_VENV_PATH: 'shared python', TEST_DATA_DIR: 'models', HF_HOME: 'hf'}));
  const a = resolveConfig({SSUI_DEV_CONFIG: configPath}, path.join(dir, 'feature-a'));
  const b = resolveConfig({SSUI_DEV_CONFIG: configPath}, path.join(dir, 'feature-b'));
  assert.equal(a.SSUI_VENV_PATH, b.SSUI_VENV_PATH);
  assert.equal(a.TEST_DATA_DIR, b.TEST_DATA_DIR);
  assert.equal(a.HF_HOME, path.join(dir, 'hf'));
  assert.notEqual(a.PYTHONPATH, b.PYTHONPATH);
  const isolated = resolveConfig({SSUI_DEV_CONFIG: configPath, SSUI_VENV_PATH: '.venv'}, path.join(dir, 'feature-b'));
  assert.equal(isolated.SSUI_VENV_PATH, path.join(dir, 'feature-b', '.venv'));
  assert.equal(isolated.TEST_DATA_DIR, a.TEST_DATA_DIR);
});
test('local config and explicit environment precedence', t => {
  const repo = fixture(t);
  fs.writeFileSync(path.join(repo, '.ssui-dev.json'), JSON.stringify({SSUI_MODEL_DIR: 'local models'}));
  assert.equal(resolveConfig({}, repo, path.join(repo, 'empty-home')).SSUI_MODEL_DIR, path.join(repo, 'local models'));
  assert.equal(resolveConfig({SSUI_MODEL_DIR: 'override'}, repo, path.join(repo, 'empty-home')).SSUI_MODEL_DIR, path.join(repo, 'override'));
  assert.throws(() => resolveConfig({SSUI_DEV_CONFIG: 'missing.json'}, repo), /does not exist/);
  fs.writeFileSync(path.join(repo, '.ssui-dev.json'), '{bad');
  assert.throws(() => resolveConfig({}, repo, path.join(repo, 'empty-home')));
});
test('launcher propagates environment and exit codes with paths containing spaces', t => {
  const dir = fixture(t);
  const venv = path.join(dir, 'shared python');
  const bin = path.dirname(executable('node', {SSUI_VENV_PATH: venv}));
  fs.mkdirSync(bin, {recursive: true});
  fs.copyFileSync(process.execPath, executable('node', {SSUI_VENV_PATH: venv}));
  const child = spawnSync(process.execPath, [path.join(__dirname, 'venv.cjs'), 'node', '-e',
    'console.log(process.env.TEST_DATA_DIR); process.exit(7)'], {
      env: {...process.env, SSUI_VENV_PATH: venv, TEST_DATA_DIR: dir}, encoding: 'utf8',
    });
  assert.equal(child.status, 7, child.stderr);
  assert.equal(child.stdout.trim(), dir);
});

test('home configuration is shared automatically and local paths resolve at their own source', t => {
  const home = fixture(t);
  fs.mkdirSync(path.join(home, '.ssui-dev'));
  fs.writeFileSync(path.join(home, '.ssui-dev', 'config.json'), JSON.stringify({SSUI_VENV_PATH: 'venv', TEST_DATA_DIR: '../models'}));
  const a = path.join(home, 'a');
  const b = path.join(home, 'b');
  fs.mkdirSync(a); fs.mkdirSync(b);
  assert.equal(resolveConfig({}, a, home).SSUI_VENV_PATH, path.join(home, '.ssui-dev', 'venv'));
  assert.equal(resolveConfig({}, a, home).SSUI_VENV_PATH, resolveConfig({}, b, home).SSUI_VENV_PATH);
  fs.writeFileSync(path.join(b, '.ssui-dev.json'), JSON.stringify({SSUI_VENV_PATH: '.venv'}));
  assert.equal(resolveConfig({}, b, home).SSUI_VENV_PATH, path.join(b, '.venv'));
  assert.equal(resolveConfig({}, b, home).TEST_DATA_DIR, path.join(home, 'models'));
});
