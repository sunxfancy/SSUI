import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';

const defaultBinary = path.resolve(
  'desktop/src-tauri/target/debug',
  process.platform === 'win32' ? 'ssui.exe' : 'ssui',
);

let tauriDriver;

export const config = {
  host: '127.0.0.1',
  port: 4444,
  specs: ['./tests/tauri-e2e/specs/**/*.spec.mjs'],
  maxInstances: 1,
  capabilities: [{
    maxInstances: 1,
    'tauri:options': {
      application: process.env.SSUI_TAURI_BINARY || defaultBinary,
    },
  }],
  framework: 'mocha',
  reporters: ['spec'],
  mochaOpts: { timeout: 60_000 },
  connectionRetryTimeout: 120_000,
  beforeSession() {
    const executable = process.env.SSUI_TAURI_DRIVER || path.join(
      os.homedir(),
      '.cargo',
      'bin',
      process.platform === 'win32' ? 'tauri-driver.exe' : 'tauri-driver',
    );
    tauriDriver = spawn(executable, [], { stdio: 'inherit' });
  },
  afterSession() {
    tauriDriver?.kill();
    tauriDriver = undefined;
  },
};
