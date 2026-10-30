const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { config, getRuntime } = require('../runtime.cjs');

test('six desktop runtime configurations have existing lock files', () => {
  assert.equal(Object.keys(config.targets).length, 6);
  for (const [id, target] of Object.entries(config.targets)) {
    assert.ok(fs.existsSync(path.join(__dirname, '..', target.lockFile)), id);
    assert.match(target.pythonTarget, /^(x86_64|aarch64)-/);
  }
});
test('Linux ARM and Intel macOS select separate native dependency locks', () => {
  assert.equal(getRuntime('linux', 'arm64').lockFile, 'linux-arm64.lock');
  assert.equal(getRuntime('darwin', 'x64').lockFile, 'macosx-x86_64.lock');
  assert.equal(getRuntime('darwin', 'arm64').lockFile, 'macosx.lock');
  assert.equal(getRuntime('linux', 'x64').lockFile, 'linux.lock');
});
test('Tauri and Node architecture names resolve identically', () => {
  assert.deepEqual(getRuntime('windows', 'aarch64'), getRuntime('win32', 'arm64'));
  assert.deepEqual(getRuntime('macos', 'x86_64'), getRuntime('darwin', 'x64'));
});
test('unsupported and 32 bit platforms fail instead of selecting a default', () => {
  for (const [os, cpu] of [['linux', 'ia32'], ['win32', 'arm'], ['android', 'arm64']]) {
    assert.throws(() => getRuntime(os, cpu), /Unsupported/);
  }
});
