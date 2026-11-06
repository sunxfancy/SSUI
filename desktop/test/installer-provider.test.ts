import { expect, it, vi } from 'vitest';
import runtimeConfig from '../../dependencies/runtime-targets.json';
const { invoke, writeTextFile } = vi.hoisted(() => ({ invoke: vi.fn(), writeTextFile: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke }));
vi.mock('@tauri-apps/api/path', () => ({ join: async (...parts: string[]) => parts.join('/'),
  dirname: async (p: string) => p.slice(0, p.lastIndexOf('/')), resolveResource: async (p: string) => '/bundle/' + p }));
vi.mock('@tauri-apps/plugin-fs', () => ({ exists: async () => true, writeTextFile }));
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
