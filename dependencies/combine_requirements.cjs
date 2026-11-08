const { execFileSync } = require('child_process');
const path = require('path');
const { getCurrentTarget } = require('./platform.cjs');
const root = path.resolve(__dirname, '..');
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
execFileSync(python, [path.join(__dirname, 'combine_requirements.py'), '--target', getCurrentTarget(), '--output', path.join(root, '.venv/requirements.txt')], { stdio: 'inherit', cwd: root });
