#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');
const isWin = process.platform === 'win32';

// 根据操作系统选择正确的路径
const current_path = path.resolve(__dirname, '..');
const venvPath = isWin ? path.join(current_path, '.venv', 'Scripts') : path.join(current_path, '.venv', 'bin');
const cmd = path.join(venvPath, process.argv[2]);

var detached = false;
if (process.argv[2] === 'fastapi') {
    detached = true;
}

// 获取传递给脚本的其余参数
const args = process.argv.slice(3);

// 执行命令
const proc = spawn(cmd, args, { stdio: 'inherit', shell: false, detached: detached, windowsHide: true });
proc.on('exit', code => process.exit(code)); 