import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

test('Cargo exposes only the production binary to the Tauri bundler', () => {
  const manifest = fileURLToPath(new URL('../../src-tauri/Cargo.toml', import.meta.url));
  const result = spawnSync('cargo', ['metadata', '--offline', '--no-deps', '--format-version', '1', '--manifest-path', manifest], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const project = JSON.parse(result.stdout).packages.find(pkg => pkg.name === 'ssui');
  assert.deepEqual(project.targets.filter(target => target.kind.includes('bin')).map(target => target.name), ['ssui']);
  const harness = project.targets.find(target => target.name === 'ssui-native-test');
  assert.deepEqual(harness.kind, ['example']);
  assert.ok(harness['required-features'].includes('native-tests'));
});
