const { platform } = require('os');
const { execSync } = require('child_process');

// 所有支持的构建目标（平台 + 可选 GPU 变体），对应 requirements-<target>.txt / <target>.lock
const ALL_TARGETS = ['windows', 'windows-amdgpu', 'macosx', 'linux', 'linux-amdgpu'];

// 拥有 AMD GPU 变体的平台
const AMDGPU_PLATFORMS = ['windows', 'linux'];

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
  return [...ALL_TARGETS];
}

// 当前平台下的所有目标（含 GPU 变体），用于在本机生成全部变体的锁文件
function getCurrentPlatformTargets() {
  const plat = getPlatform();
  return getAllTargets().filter(t => t === plat || t.startsWith(`${plat}-`));
}

// 根据平台 + GPU 推断当前应使用的目标名
// AMD GPU 使用 <platform>-amdgpu 变体，其余（nvidia / intel / unknown）回退到默认平台目标
function getCurrentTarget() {
  const plat = getPlatform();
  const gpu = getGPU();
  if (gpu === 'amd' && AMDGPU_PLATFORMS.includes(plat)) {
    return `${plat}-amdgpu`;
  }
  return plat;
}

module.exports = {
  getPlatform,
  getGPU,
  parseVendor,
  getAllTargets,
  getCurrentPlatformTargets,
  getCurrentTarget,
};
