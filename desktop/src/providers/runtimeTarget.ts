import config from '../../../dependencies/runtime-targets.json';

export interface RuntimeTarget {
  os: 'windows' | 'linux' | 'macos';
  arch: 'x64' | 'arm64';
  backend: 'cpu' | 'cuda' | 'rocm' | 'mps' | 'qnn';
}

export function makeRuntimeTarget(os: string, architecture: string, gpu = 'unknown'): RuntimeTarget {
  const normalizedOS = ({ win32: 'windows', darwin: 'macos', macosx: 'macos' } as Record<string, string>)[os] || os;
  const arch = ({ x86_64: 'x64', amd64: 'x64', aarch64: 'arm64' } as Record<string, string>)[architecture.toLowerCase()] || architecture.toLowerCase();
  if (!config.oses.includes(normalizedOS) || !config.architectures.includes(arch)) {
    throw new Error(`不支持的系统或 CPU 架构: ${os} / ${architecture}`);
  }
  const backend = normalizedOS === 'macos' ? (arch === 'arm64' ? 'mps' : 'cpu')
    : arch === 'arm64' ? 'cpu' : gpu.toLowerCase() === 'amd' ? 'rocm' : 'cuda';
  return { os: normalizedOS, arch, backend } as RuntimeTarget;
}

export function dependencyProfile(target: RuntimeTarget) {
  const profile = config.profiles.find(p => p.os === target.os && p.arch === target.arch && p.backend === target.backend);
  if (!profile) throw new Error(`尚未提供 ${target.os}-${target.arch}-${target.backend} 的依赖配置；不会回退到其他架构或计算后端`);
  return profile;
}

export function pythonDistribution(target: RuntimeTarget) {
  const profile = dependencyProfile(target);
  return { ...config.python, ...profile.python, triple: config.triples[target.os][target.arch] };
}
