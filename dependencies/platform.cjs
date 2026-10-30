const { platform } = require('os');
const { execSync } = require('child_process');

const { config, detectRuntime, dependencyProfile } = require('./runtime_target.cjs');

// 获取当前平台名
function getPlatform() {
  const os = platform();
  switch (os) {
    case 'win32':
      return 'windows';
    case 'darwin':
      return 'macosx';
    case 'linux':
      return 'linux';
    default:
      throw new Error(`不支持的操作系统平台: ${os}`);
  }
}

// 从文本中解析 GPU 厂商
function parseVendor(text) {
  const s = (text || '').toLowerCase();
  if (/nvidia|geforce|rtx|gtx|quadro|tesla/.test(s)) return 'nvidia';
  if (/amd|radeon|advanced micro devices|\bati\b/.test(s)) return 'amd';
  if (/intel|arc|iris|uhd graphics/.test(s)) return 'intel';
  return 'unknown';
}

// 检测当前机器的 GPU 厂商
function getGPU() {
  const os = platform();
  try {
    if (os === 'win32') {
      const out = execSync(
        'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"',
        { encoding: 'utf8' }
      );
      return parseVendor(out);
    } else if (os === 'linux') {
      // 优先用 PCI vendor id，避免依赖 lspci 是否安装
      try {
        const ids = execSync(
          'cat /sys/class/drm/card*/device/vendor 2>/dev/null',
          { encoding: 'utf8', shell: '/bin/bash' }
        );
        if (/0x10de/i.test(ids)) return 'nvidia';
        if (/0x1002/i.test(ids)) return 'amd';
        if (/0x8086/i.test(ids)) return 'intel';
      } catch (_) { /* 回退到 lspci */ }
      const out = execSync('lspci', { encoding: 'utf8' });
      const lines = out.split('\n').filter(l => /vga|3d|display/i.test(l)).join(' ');
      return parseVendor(lines);
    } else if (os === 'darwin') {
      const out = execSync('system_profiler SPDisplaysDataType', { encoding: 'utf8' });
      return parseVendor(out);
    }
  } catch (error) {
    console.warn('GPU detection failed, falling back to default:', error.message);
  }
  return 'unknown';
}

// 所有构建目标
function getAllTargets() {
  return config.profiles.map(p => p.dependencyTarget);
}

// 当前 OS + CPU 架构的依赖配置，用于生成不同后端的锁文件。
function getCurrentPlatformTargets() {
  const { target } = detectRuntime();
  return config.profiles.filter(p => p.os === target.os && p.arch === target.arch)
    .map(p => p.dependencyTarget);
}

// 兼容现有调用方：三维目标经注册表映射为已有依赖文件名。
function getCurrentTarget() {
  return dependencyProfile(getRuntimeTarget()).dependencyTarget;
}

function getRuntimeTarget() {
  return detectRuntime({ gpu: process.env.SSUI_COMPUTE_BACKEND ? 'unknown' : getGPU() }).target;
}

module.exports = {
  getPlatform,
  getGPU,
  parseVendor,
  getAllTargets,
  getCurrentPlatformTargets,
  getCurrentTarget,
  getRuntimeTarget,
};
