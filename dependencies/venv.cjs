#!/usr/bin/env node
const { spawn } = require('child_process');
const { resolveConfig, executable } = require('./dev_config.cjs');
const env = resolveConfig();
const name = process.argv[2];
if (!name) {
  console.error('Usage: node dependencies/venv.cjs <command> [args]');
  process.exit(1);
}
const proc = spawn(executable(name, env), process.argv.slice(3), {
  stdio: 'inherit', shell: false, windowsHide: true, env,
});
proc.on('error', error => {
  console.error(`Cannot run ${name} in ${env.SSUI_VENV_PATH}: ${error.message}`);
  process.exit(1);
});
proc.on('exit', code => process.exit(code === null ? 1 : code));
