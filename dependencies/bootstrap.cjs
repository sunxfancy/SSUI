// Shared native Python bootstrap for developer installs on all six desktops.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { getRuntime } = require('./runtime.cjs');
const root = path.resolve(__dirname, '..');
const runtime = getRuntime();
const windows = process.platform === 'win32';
function run(command, args) {
  const p = spawnSync(command, args, { cwd: root, stdio: 'inherit' });
  if (p.error || p.status !== 0) throw p.error || new Error(`${command} failed (${p.status})`);
}
const base = path.join(root, '.venv', 'python', windows ? 'python.exe' : 'bin/python3');
const python = path.join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python3');
fs.mkdirSync(path.join(root, '.venv'), { recursive: true });
if (!fs.existsSync(base)) {
  const name = `cpython-${runtime.pythonVersion}+${runtime.pythonRelease}-${runtime.pythonTarget}-install_only_stripped.tar.gz`;
  const archive = path.join(root, '.venv', 'python.tar.gz');
  run('curl', ['--fail', '--location', '--retry', '3', `https://github.com/astral-sh/python-build-standalone/releases/download/${runtime.pythonRelease}/${name}`, '-o', archive]);
  run('tar', ['-xzf', archive, '-C', path.join(root, '.venv')]);
  fs.unlinkSync(archive);
}
if (!fs.existsSync(python)) run(base, ['-m', 'venv', path.join(root, '.venv')]);
run(python, ['-m', 'pip', 'install', `uv==${runtime.uvVersion}`, 'packaging==24.1']);
