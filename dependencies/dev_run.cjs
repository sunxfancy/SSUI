const { spawn } = require('child_process');
const { resolveConfig, root } = require('./dev_config.cjs');
if (!process.env.npm_execpath) throw new Error('Run this command through yarn');
const child = spawn(process.execPath, [process.env.npm_execpath, ...process.argv.slice(2)], {
  cwd: root, env: resolveConfig(), stdio: 'inherit', windowsHide: true,
});
child.on('error', error => { console.error(error.message); process.exit(1); });
child.on('exit', code => process.exit(code === null ? 1 : code));
