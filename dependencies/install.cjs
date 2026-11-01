#!/usr/bin/env node

const { execSync, execFileSync } = require('child_process');
const { platform } = require('os');
const { join } = require('path');
const { existsSync } = require('fs');

/**
 * 根据当前平台执行相应的安装脚本
 */
function runInstallScript() {
  // 检查是否设置了跳过安装的环境变量
  if (process.env.SSUI_CI_SKIP_INSTALL === '1') {
    console.log('检测到 SSUI_CI_SKIP_INSTALL=1，跳过安装过程');
    process.exit(0);
  }

  try {
    // 获取当前工作目录
    const rootDir = join(__dirname, '..');
    
    // 检测操作系统类型
    const isWindows = platform() === 'win32';
    
    // 确定脚本路径
    const scriptPath = isWindows 
      ? join(rootDir, 'dependencies', 'install.cmd')
      : join(rootDir, 'dependencies', 'install.sh');
    
    // 检查脚本是否存在
    if (!existsSync(scriptPath)) {
      console.error(`错误: 安装脚本不存在: ${scriptPath}`);
      process.exit(1);
    }
    
    console.log(`开始执行安装脚本: ${scriptPath}`);
    
    // 执行相应的安装脚本
    if (isWindows) {
      execSync(`"${scriptPath}"`, { stdio: 'inherit', cwd: rootDir });
    } else {
      execFileSync('bash', [scriptPath], { stdio: 'inherit', cwd: rootDir });
    }

    execSync('yarn requirements', { stdio: 'inherit', cwd: rootDir });
    execSync('yarn install-requirements', { stdio: 'inherit', cwd: rootDir });
    
    console.log('安装脚本执行完成');
  } catch (error) {
    console.error('安装脚本执行失败:', error.message);
    process.exit(1);
  }
}

// 执行安装脚本
runInstallScript();