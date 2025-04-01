#!/usr/bin/env node

const { execSync } = require('child_process');
const { platform } = require('os');
const { join } = require('path');
const { existsSync } = require('fs');

/**
 * 根据当前平台执行相应的安装脚本
 */
function runInstallScript() {
  try {
    // 获取当前工作目录
    const rootDir = process.cwd();
    
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
      execSync(scriptPath, { stdio: 'inherit' });
    } else {
      // 确保shell脚本有执行权限
      execSync(`chmod +x "${scriptPath}"`, { stdio: 'inherit' });
      execSync(scriptPath, { stdio: 'inherit' });
    }
    
    console.log('安装脚本执行完成');
  } catch (error) {
    console.error('安装脚本执行失败:', error.message);
    process.exit(1);
  }
}

// 执行安装脚本
runInstallScript();