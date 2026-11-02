import { mockIPC } from '@tauri-apps/api/mocks';

type State = { calls: { command: string; args: unknown }[]; fail: boolean; delay: number; running: boolean };
const state: State = { calls: [], fail: false, delay: 0, running: false };
(window as unknown as { ipcFixture: State }).ipcFixture = state;
mockIPC(async (command, args) => {
  state.calls.push({ command, args });
  if (state.delay) await new Promise(resolve => setTimeout(resolve, state.delay));
  if (state.fail) throw new Error('fixture permission denied');
  if (command.startsWith('start_') || command.startsWith('restart_')) {
    state.running = true; return { pid: '42' };
  }
  if (command.startsWith('stop_')) { state.running = false; return true; }
  if (command.startsWith('get_') && command.endsWith('_status')) {
    return { is_running: state.running, pid: state.running ? '42' : null };
  }
  throw new Error(`Unmocked IPC command: ${command}`);
});
