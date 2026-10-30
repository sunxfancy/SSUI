import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TauriProcessProvider, type ProcessEnvironment } from '../src/providers/TauriProcessProvider';

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke }));

describe.each(['server', 'executor'] as const)('%s IPC contract', kind => {
  let provider: TauriProcessProvider;
  let environment: ProcessEnvironment;
  beforeEach(() => {
    invoke.mockReset();
    environment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      rootPath: () => '/安装 & data',
      pythonPath: vi.fn().mockResolvedValue('/安装 & data/python'),
    };
    provider = new TauriProcessProvider(kind, kind, environment);
  });
  it('awaits initialization and sends exact executable/cwd', async () => {
    invoke.mockResolvedValue({ pid: '42' });
    expect((await provider.start()).success).toBe(true);
    expect(environment.initialize).toHaveBeenCalledOnce();
    expect(invoke).toHaveBeenCalledWith(`start_${kind}`, { path: '/安装 & data/python', cwd: '/安装 & data' });
  });
  it('does not submit two concurrent lifecycle operations', async () => {
    let resolve!: (value: unknown) => void;
    invoke.mockReturnValue(new Promise(r => { resolve = r; }));
    const first = provider.start();
    await vi.waitFor(() => expect(invoke).toHaveBeenCalledOnce());
    expect((await provider.start()).success).toBe(false);
    expect((await provider.restart()).success).toBe(false);
    expect((await provider.stop()).success).toBe(false);
    resolve({ pid: '42' });
    expect((await first).success).toBe(true);
    expect(invoke).toHaveBeenCalledOnce();
  });
  it('queries real backend state even when provider has no cached PID', async () => {
    invoke.mockResolvedValueOnce({ is_running: true, pid: '73' });
    expect((await provider.status()).message).toContain('73');
    invoke.mockResolvedValueOnce({ is_running: false, pid: null });
    expect((await provider.status()).message).toContain('未在运行中');
    expect(invoke).toHaveBeenLastCalledWith(`get_${kind}_status`);
  });
  it('uses the registered stop command and treats false as failure', async () => {
    invoke.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    expect((await provider.stop()).success).toBe(false);
    expect((await provider.stop()).success).toBe(true);
    expect(invoke).toHaveBeenLastCalledWith(`stop_${kind}`);
  });
  it('releases operation lock after rejection and permits retry', async () => {
    invoke.mockRejectedValueOnce(new Error('permission denied')).mockResolvedValueOnce({ pid: '88' });
    expect(await provider.start()).toMatchObject({ success: false, message: expect.stringContaining('permission denied') });
    expect((await provider.start()).success).toBe(true);
  });
  it('rejects malformed PID and malformed status', async () => {
    invoke.mockResolvedValueOnce({ pid: 'invalid' }).mockResolvedValueOnce(true);
    expect((await provider.start()).success).toBe(false);
    expect((await provider.status()).success).toBe(false);
  });
  it('does not invoke a process command without an installation', async () => {
    environment.rootPath = () => null;
    expect((await provider.restart()).success).toBe(false);
    expect(invoke).not.toHaveBeenCalled();
  });
});
