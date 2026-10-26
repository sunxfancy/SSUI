import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { TauriDownloaderProvider } from '../src/providers/TauriDownloaderProvider';
import type { CivitaiModel } from '../src/types/civitai';

const { invoke, listen, handlers, unlisteners } = vi.hoisted(() => ({
  invoke: vi.fn(), listen: vi.fn(),
  handlers: new Map<string, (event: { payload: unknown }) => void>(), unlisteners: [] as ReturnType<typeof vi.fn>[],
}));
vi.mock('@tauri-apps/api/core', () => ({ invoke }));
vi.mock('@tauri-apps/api/event', () => ({ listen }));
vi.mock('../src/services/GlobalState', () => ({ default: {
  getInstance: () => ({ getRootState: () => ({ path: '/安装 path' }) }),
} }));

let provider: TauriDownloaderProvider;
const model = { id: 9, type: 'Checkpoint', modelVersions: [{ files: [{
  id: 17, name: 'model.bin', downloadUrl: 'https://example.test/model?token=fixture',
  metadata: { format: 'SafeTensor', fp: 'fp16' },
}] }] } as unknown as CivitaiModel;

beforeEach(() => {
  invoke.mockReset().mockResolvedValue([]); listen.mockReset(); handlers.clear(); unlisteners.length = 0;
  listen.mockImplementation(async (name, handler) => {
    handlers.set(name, handler); const stop = vi.fn(); unlisteners.push(stop); return stop;
  });
});
afterEach(() => provider?.destroy());

it('uses the actual URL for progress, early completion and cancellation', async () => {
  const changed = vi.fn(); provider = new TauriDownloaderProvider(changed);
  await provider.getDownloadTasks();
  let url = '';
  invoke.mockImplementation(async (command, args) => {
    if (command === 'create_download_task') {
      url = args.url;
      handlers.get('download-progress')!({ payload: { url, progress: 1, total: 4 } });
      expect((await provider.getDownloadTask('9'))?.progress).toBe(25);
      handlers.get('download-completed')!({ payload: url });
    }
  });
  const task = await provider.addDownloadTask(model, 17);
  expect(task).toMatchObject({ status: 'completed', progress: 100 });
  expect(new URL(url).searchParams.get('token')).toBe('fixture');
  expect(new URL(url).searchParams.get('format')).toBe('SafeTensor');
  expect(changed).toHaveBeenCalledTimes(2);
  expect(await provider.cancelDownloadTask('9')).toBe(true);
  expect(invoke).toHaveBeenLastCalledWith('cancel_download_task', { url });
});

it('maps failure and cancellation events using URL rather than model ID', async () => {
  provider = new TauriDownloaderProvider(); await provider.getDownloadTasks();
  await provider.addDownloadTask(model);
  const url = invoke.mock.calls.find(([command]) => command === 'create_download_task')![1].url;
  handlers.get('download-failed')!({ payload: { url, error: 'SHA256 mismatch' } });
  expect(await provider.getDownloadTask('9')).toMatchObject({ status: 'failed', error: 'SHA256 mismatch' });
  handlers.get('download-cancelled')!({ payload: url });
  expect(await provider.getDownloadTask('9')).toMatchObject({ status: 'failed', error: '下载已取消' });
});

it('releases listeners that resolve after the owning component is destroyed', async () => {
  let resolve!: (stop: () => void) => void;
  const late = vi.fn();
  listen.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  provider = new TauriDownloaderProvider(); provider.destroy();
  resolve(late);
  await vi.waitFor(() => expect(listen).toHaveBeenCalledTimes(4));
  await provider.getDownloadTasks();
  expect(late).toHaveBeenCalledOnce();
  for (const stop of unlisteners) expect(stop).toHaveBeenCalledOnce();
  provider.destroy();
  expect(late).toHaveBeenCalledOnce();
});

it('restores block progress as a percentage and cancels restored URL tasks', async () => {
  const url = 'https://example.test/restored';
  invoke.mockResolvedValue([{ url, output_path: 'model.bin', status: 'Downloading', progress: 2, total_blocks: 8 }]);
  provider = new TauriDownloaderProvider();
  expect((await provider.getDownloadTasks())[0].progress).toBe(25);
  expect(await provider.cancelDownloadTask(url)).toBe(true);
  expect(invoke).toHaveBeenLastCalledWith('cancel_download_task', { url });
});
