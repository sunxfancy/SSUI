#!/usr/bin/env node

const { resolveConfig } = require('./dev_config.cjs');
Object.assign(process.env, resolveConfig());

const { execSync, execFileSync } = require('child_process');
const { platform } = require('os');
const { join } = require('path');
const { executable } = require('./dev_config.cjs');
const { existsSync } = require('fs');
const { getCurrentTarget, getRuntimeTarget } = require('./platform.cjs');
const { dependencyProfile, pythonDistribution } = require('./runtime_target.cjs');

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
    // Fail before downloading Python when no matching dependency profile exists.
    getCurrentTarget();
    const target = getRuntimeTarget();
    const python = pythonDistribution(target);
    process.env.SSUI_PYTHON_TRIPLE = python.triple;
    process.env.SSUI_PYTHON_VERSION = python.version;
    process.env.SSUI_PYTHON_RELEASE = python.release;
    process.env.SSUI_UV_VERSION = dependencyProfile(target).uvVersion || '0.6.11';
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

    // Existing environments may still contain the older resolver. ARM64 target
    // parsing requires the profile's newer uv even if uv.exe already exists.
    const requiredUv = dependencyProfile(target).uvVersion;
    if (requiredUv) {
      const currentUv = execFileSync(executable('uv', process.env), ['--version'], { encoding: 'utf8' }).trim().split(/\s+/)[1];
      if (currentUv !== requiredUv) {
        execFileSync(executable('python', process.env), ['-m', 'pip', 'install', `uv==${requiredUv}`], { stdio: 'inherit' });
      }
    }

    execSync('yarn requirements', { stdio: 'inherit' });
    execSync('yarn install-requirements', { stdio: 'inherit' });
    
    console.log('安装脚本执行完成');
  } catch (error) {
    console.error('安装脚本执行失败:', error.message);
    process.exit(1);
  }
}

// 执行安装脚本
runInstallScript();
