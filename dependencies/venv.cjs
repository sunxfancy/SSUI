#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { resolveConfig, executable } = require('./dev_config.cjs');
const env = resolveConfig();
const name = process.argv[2];
if (!name) {
  console.error('Usage: node dependencies/venv.cjs <command> [args]');
  process.exit(1);
}
const native = path.join(__dirname, 'native_cuda.py');
const local = path.resolve(env.SSUI_VENV_PATH) === path.resolve(__dirname, '../.venv');
const managed = process.platform === 'linux' && local && fs.existsSync(native);
const command = executable(name, env);
const args = process.argv.slice(3);
const proc = spawn(managed ? executable('python', env) : command, managed ? [native, 'exec', '--', command, ...args] : args, {
  stdio: 'inherit', shell: false, windowsHide: true, env,
});
proc.on('error', error => {
  console.error(`Cannot run ${name} in ${env.SSUI_VENV_PATH}: ${error.message}`);
  process.exit(1);
});
proc.on('exit', code => process.exit(code === null ? 1 : code));
