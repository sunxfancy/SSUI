import { expect, it, vi } from 'vitest';
import runtimeConfig from '../../dependencies/runtime-targets.json';
const { invoke, writeTextFile, readDir, save, set } = vi.hoisted(() => ({ invoke: vi.fn(), writeTextFile: vi.fn(), readDir: vi.fn(), save: vi.fn(), set: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke }));
vi.mock('@tauri-apps/api/path', () => ({ join: async (...parts: string[]) => parts.join('/'),
  dirname: async (p: string) => p.slice(0, p.lastIndexOf('/')), resolveResource: async (p: string) => '/bundle/' + p }));
vi.mock('@tauri-apps/plugin-fs', () => ({ exists: async () => true, writeTextFile, readDir }));
vi.mock('@tauri-apps/plugin-store', () => ({ load: async () => ({save, set}) }));
vi.mock('@tauri-apps/plugin-os', () => ({ platform: async () => 'linux', arch: () => 'x86_64' }));
import { TauriInstallerProvider } from '../src/providers/TauriInstallerProvider';

it('does not mark Linux installed when constrained dependency installation fails', async () => {
  invoke.mockReset().mockResolvedValue(''); writeTextFile.mockReset();
  invoke.mockImplementation(async (_command, args) => {
    if (args.args.includes('--build-constraint')) throw Error('build failed');
    return '';
  });
  const result = await new TauriInstallerProvider().installPackages('/fresh install', 'linux.lock');
  expect(result.success).toBe(false);
  expect(writeTextFile).not.toHaveBeenCalled();
});

it('prepares native CUDA after the shared Linux UV installer succeeds', async () => {
  invoke.mockReset().mockResolvedValue(''); writeTextFile.mockReset();
  const result = await new TauriInstallerProvider().installPackages('/fresh install', 'linux.lock');
  expect(result.success).toBe(true);
  const args = invoke.mock.calls.map(([, params]) => params.args);
  expect(args[0]).toEqual(['-m', 'pip', 'install', `uv==${runtimeConfig.uvVersion}`]);
  expect(args[1]).toContain('--build-constraint');
  expect(args[1]).toContain('/fresh install/.venv/bin/python');
  expect(args[2]).toContain('/bundle/resources/dependencies/native_cuda.py');
  expect(writeTextFile).toHaveBeenCalledWith('/fresh install/.venv/.packages_installed', 'base-v2');
});

it('unpacks only extension archives before saving the installation', async () => {
  invoke.mockReset().mockResolvedValue('success'); save.mockReset(); set.mockReset();
  readDir.mockResolvedValue([
    {name: 'Readme.md', isFile: true},
    {name: 'cache.tar.gz', isFile: false},
    {name: 'Video-0.1.0.tar.gz', isFile: true},
  ]);
  await new TauriInstallerProvider().saveSettings({path: '/fresh install', version: '0.3.0', platform: 'linux'});
  expect(invoke.mock.calls.map(([, args]) => args.tar_path)).toEqual([
    '/bundle/resources/app.tar.gz', '/bundle/resources/extensions/Video-0.1.0.tar.gz',
  ]);
  expect(save).toHaveBeenCalledOnce();
});
