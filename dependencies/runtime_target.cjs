// OS, CPU architecture and compute backend are independent dimensions.
// Profiles only describe dependency sets that already exist, not all valid targets.
const config = require('./runtime-targets.json');

function normalizeOS(value) {
  const os = ({ win32: 'windows', darwin: 'macos', macosx: 'macos' })[value] || value;
  if (!config.oses.includes(os)) throw new Error(`不支持的操作系统: ${value}`);
  return os;
}

function normalizeArch(value) {
  const arch = ({ x86_64: 'x64', amd64: 'x64', aarch64: 'arm64' })[String(value).toLowerCase()] || String(value).toLowerCase();
  if (!config.architectures.includes(arch)) throw new Error(`不支持的 CPU 架构: ${value}`);
  return arch;
}

function runtimeTarget(os, arch, backend) {
  if (!config.backends.includes(backend)) throw new Error(`不支持的计算后端: ${backend}`);
  return { os: normalizeOS(os), arch: normalizeArch(arch), backend };
}

function targetName(target) {
  const { os, arch, backend } = runtimeTarget(target.os, target.arch, target.backend);
  return `${os}-${arch}-${backend}`;
}

function dependencyProfile(target) {
  const normalized = runtimeTarget(target.os, target.arch, target.backend);
  const profile = config.profiles.find(p => p.os === normalized.os && p.arch === normalized.arch && p.backend === normalized.backend);
  if (!profile) throw new Error(`尚未提供 ${targetName(normalized)} 的依赖配置；不会回退到其他架构或计算后端`);
  return { ...profile };
}

function profileFromName(name) {
  const profile = config.profiles.find(p => p.dependencyTarget === name || targetName(p) === name);
  if (!profile) throw new Error(`未知或尚未提供依赖的目标: ${name}`);
  return { ...profile };
}

function pythonTriple(target) {
  return config.triples[normalizeOS(target.os)][normalizeArch(target.arch)];
}

function pythonDistribution(target) {
  const profile = dependencyProfile(target);
  return { ...config.python, ...profile.python, triple: pythonTriple(target) };
}

function assertPythonRuntime(target, pythonRuntime) {
  if (normalizeOS(pythonRuntime.os) !== target.os || normalizeArch(pythonRuntime.arch) !== target.arch) {
    throw new Error(`Python 的 OS / 架构与 ${targetName(target)} 不匹配，请使用目标系统和架构的 Python`);
  }
}

// Keep host, process and requested target separate. An x64 process on ARM Windows
// must use x64 Python unless the user explicitly selects a native ARM target.
function detectRuntime({ os = process.platform, arch = process.arch, env = process.env, gpu = 'unknown' } = {}) {
  const processArch = normalizeArch(arch);
  const hostArch = os === 'win32' || os === 'windows'
    ? normalizeArch(env.PROCESSOR_ARCHITEW6432 || env.PROCESSOR_ARCHITECTURE || arch)
    : processArch;
  const targetOS = normalizeOS(env.SSUI_TARGET_OS || os);
  const targetArch = normalizeArch(env.SSUI_TARGET_ARCH || arch);
  // CUDA is the existing x64 dependency distribution (also used for CPU
  // fallback by PyTorch). This is a package choice, not proof of GPU availability.
  const backend = env.SSUI_COMPUTE_BACKEND || (targetOS === 'macos'
    ? (targetArch === 'arm64' ? 'mps' : 'cpu')
    : (targetArch === 'arm64' ? 'cpu' : gpu === 'amd' ? 'rocm' : 'cuda'));
  return { hostArch, processArch, target: runtimeTarget(targetOS, targetArch, backend) };
}

module.exports = { config, normalizeOS, normalizeArch, runtimeTarget, targetName, dependencyProfile, profileFromName, pythonTriple, pythonDistribution, assertPythonRuntime, detectRuntime };
