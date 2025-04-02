#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');
const isWin = process.platform === 'win32';

// 根据操作系统选择正确的路径
const venvPath = isWin ? '.venv/Scripts' : '.venv/bin';
const cmd = path.join(venvPath, process.argv[2]);

// 获取传递给脚本的其余参数
const args = process.argv.slice(3);

// 执行命令
const proc = spawn(cmd, args, { stdio: 'inherit', shell: true });
proc.on('exit', code => process.exit(code)); 