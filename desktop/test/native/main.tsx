import { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { invoke } from '@tauri-apps/api/core';
import { load } from '@tauri-apps/plugin-store';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { TauriServerProvider } from '../../src/providers/TauriServerProvider';
import { TauriExecutorProvider } from '../../src/providers/TauriExecutorProvider';
import type { CommandInfo } from '../../src/providers/IInstallerProvider';

// Isolated test entry. Uses production providers and production Rust handlers.
// Never imported by the application's main.tsx or included in production assets.
function Harness() {
  const [root, setRoot] = useState('');
  const [python, setPython] = useState('');
  const [message, setMessage] = useState('Ready');
  const [pending, setPending] = useState(false);
  const [url, setUrl] = useState('');
  const [hash, setHash] = useState('');
  const [events, setEvents] = useState<string[]>([]);
  const listeners = useRef<UnlistenFn[]>([]);
  useEffect(() => () => { listeners.current.forEach(unlisten => unlisten()); }, []);
  const environment = useMemo(() => ({
    initialize: async () => {}, rootPath: () => root,
    pythonPath: async () => python,
  }), [root, python]);
  const server = useMemo(() => new TauriServerProvider(environment), [environment]);
  const executor = useMemo(() => new TauriExecutorProvider(environment), [environment]);
  async function run(action: () => Promise<CommandInfo>) {
    setPending(true);
    try { const result = await action(); setMessage(`${result.success ? 'OK' : 'ERROR'}: ${result.message}`); }
    catch (error) { setMessage(`ERROR: ${error}`); }
    finally { setPending(false); }
  }
  return <main>
    <h1>Native command contract</h1>
    <label>Fixture directory<input id="root-path" value={root} onChange={e => setRoot(e.target.value)} /></label>
    <label>Python executable<input id="python-path" value={python} onChange={e => setPython(e.target.value)} /></label>
    <section aria-label="Process controls">
      {[
        ['server-start', () => server.startServer()], ['server-stop', () => server.stopServer()],
        ['server-restart', () => server.restartServer()], ['server-status', () => server.getServerStatus()],
        ['executor-start', () => executor.startExecutor()], ['executor-stop', () => executor.stopExecutor()],
        ['executor-restart', () => executor.restartExecutor()], ['executor-status', () => executor.getExecutorStatus()],
      ].map(([id, action]) => <button key={id as string} id={id as string} disabled={pending}
        onClick={() => void run(action as () => Promise<CommandInfo>)}>{id as string}</button>)}
    </section>
    <button id="python-run" disabled={pending} onClick={() => void run(async () => ({ success: true,
      message: await invoke<string>('run_python', { path: python, cwd: root, args: ['-c', "print('native output')"] }),
    }))}>Run Python</button>
    <button id="store-save" disabled={pending} onClick={() => void run(async () => {
      const store = await load(`${root}/settings.json`, { autoSave: false });
      await store.set('theme', 'dark'); await store.save();
      return { success: true, message: 'stored dark' };
    })}>Save setting</button>
    <button id="store-load" disabled={pending} onClick={() => void run(async () => {
      const store = await load(`${root}/settings.json`, { autoSave: false });
      return { success: true, message: `loaded ${await store.get('theme')}` };
    })}>Load setting</button>
    <label>Download URL<input id="download-url" value={url} onChange={e => setUrl(e.target.value)} /></label>
    <label>Expected SHA256<input id="download-hash" value={hash} onChange={e => setHash(e.target.value)} /></label>
    <button id="download-start" disabled={pending} onClick={() => void run(async () => {
      if (!listeners.current.length) {
        for (const name of ['download-progress', 'download-completed', 'download-failed', 'download-cancelled']) {
          listeners.current.push(await listen(name, () => setEvents(previous => [...previous, name])));
        }
      }
      await invoke('create_download_task', { url, output_path: `${root}/download.bin`, sha256: hash });
      return { success: true, message: 'download started' };
    })}>Start download</button>
    <button id="download-status" disabled={pending} onClick={() => void run(async () => ({ success: true,
      message: JSON.stringify(await invoke('get_download_task_progress', { url })),
    }))}>Download status</button>
    <button id="download-cancel" disabled={pending} onClick={() => void run(async () => {
      await invoke('cancel_download_task', { url }); return { success: true, message: 'download cancelled' };
    })}>Cancel download</button>
    <output id="download-events">{events.join(',')}</output>
    <button id="app-close" onClick={() => void getCurrentWindow().close()}>Close test app</button>
    <output id="result" aria-live="polite">{message}</output>
  </main>;
}
async function mount() {
  if (import.meta.env.MODE === 'ipc-test') await import('./mock-ipc');
  createRoot(document.getElementById('root')!).render(<Harness />);
}
void mount();
