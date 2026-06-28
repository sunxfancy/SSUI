#!/usr/bin/env node
/**
 * 将 *.lock 中列出的全部 Python 包下载到本地，并打包成一个
 * `<target>-offline-installer.pkg`（本质是 tar.gz）离线安装包。
 *
 * 设计目标：在有网络的机器上由维护者运行本脚本，把某个平台 lock 文件里
 * 锁定的所有 wheel / sdist（含 `name @ https://...` 直链与 `--extra-index-url`
 * 源里的包）一次性下载齐全，打成单个 .pkg；离线机器解压后用包内自带的
 * install-offline 脚本（或一行 pip 命令）即可完成安装，无需联网。
 *
 * 注意（跨平台限制）：
 *   pip 下载的 wheel 是按“运行本脚本的这台机器”的操作系统 / Python 版本解析的。
 *   要为某个平台产出可用的离线包，必须在“该平台 + 对应 Python 版本”的机器上运行。
 *   因此默认只处理与当前平台匹配的 lock（含 GPU 变体）。`--all` 会强行处理所有
 *   lock，但其它平台的离线包很可能不可用，仅供特殊场景使用。
 *
 * 用法：
 *   node dependencies/pack_offline.cjs [选项]
 *
 * 选项：
 *   --target <name>     只打包指定目标的 lock（windows / windows-amdgpu /
 *                       linux / linux-amdgpu / macosx）。可重复指定。
 *   --all               处理 dependencies 下所有存在的 *.lock（见上方跨平台限制）
 *   --output-dir <dir>  输出目录（默认 dist/）
 *   --keep-staging      保留打包前的中间目录（默认打包后删除）
 *   --python <path>     指定用于下载的 python 可执行文件（默认使用 .venv 内的）
 *   -h, --help          显示帮助
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DEPS_DIR = __dirname;
const isWin = process.platform === 'win32';

// python-build-standalone 版本（与 install.cmd / install.sh / 后端 download_python 保持一致）
const PYTHON_VERSION = '3.12.8';
const PYTHON_RELEASE = '20241219';

// 各打包目标对应的 Python 架构（用于下载对应的 standalone 解释器）
const TARGET_ARCH = {
  'windows': 'x86_64-pc-windows-msvc',
  'windows-amdgpu': 'x86_64-pc-windows-msvc',
  'linux': 'x86_64-unknown-linux-gnu',
  'linux-amdgpu': 'x86_64-unknown-linux-gnu',
  'macosx': 'aarch64-apple-darwin',
};

function parseArgs(argv) {
  const opts = {
    targets: [],
    all: false,
    outputDir: path.join(ROOT, 'dist'),
    keepStaging: false,
    python: null,
    noPython: false,
    help: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--target' || a === '-t') opts.targets.push(argv[++i]);
    else if (a === '--all' || a === '-a') opts.all = true;
    else if (a === '--output-dir' || a === '-o') opts.outputDir = path.resolve(argv[++i]);
    else if (a === '--keep-staging') opts.keepStaging = true;
    else if (a === '--python') opts.python = argv[++i];
    else if (a === '--no-python') opts.noPython = true;
    else if (a === '-h' || a === '--help') opts.help = true;
    else console.warn(`忽略未知参数: ${a}`);
  }
  return opts;
}

function printHelp() {
  console.log(`将 *.lock 中的 Python 包下载并打包为离线安装包(.pkg / tar.gz)

用法: node dependencies/pack_offline.cjs [选项]

选项:
  --target, -t <name>   只打包指定目标的 lock(可重复)，如 windows / windows-amdgpu /
                        linux / linux-amdgpu / macosx
  --all, -a             处理所有存在的 *.lock(其它平台的包通常不可用，慎用)
  --output-dir, -o <d>  输出目录(默认 dist/)
  --keep-staging        保留打包前的中间目录
  --python <path>       指定下载用的 python(默认 .venv 内的解释器)
  --no-python           不把 Python 解释器(python-build-standalone)纳入离线包
  -h, --help            显示本帮助

默认行为: 只处理与当前平台匹配的 lock(含 GPU 变体)，并随包附带对应平台的 Python。

离线机器使用方式:
  解压 <target>-offline-installer.pkg 后，运行其中的
  install-offline.cmd(Windows) 或 install-offline.sh(Linux/macOS)，
  或手动执行:
    pip install --no-index --find-links packages -r <target>.lock`);
}

// 选出要处理的目标列表
function resolveTargets(opts) {
  const { getAllTargets, getCurrentPlatformTargets } = require('./platform.cjs');

  let candidates;
  if (opts.targets.length > 0) {
    candidates = opts.targets;
  } else if (opts.all) {
    candidates = getAllTargets();
  } else {
    candidates = getCurrentPlatformTargets();
  }

  const result = [];
  for (const t of candidates) {
    const lockFile = path.join(DEPS_DIR, `${t}.lock`);
    if (fs.existsSync(lockFile)) {
      result.push({ target: t, lockFile });
    } else {
      console.warn(`跳过目标 ${t}: 未找到锁文件 ${lockFile}`);
    }
  }
  return result;
}

// 定位用于下载的 python 解释器
function resolvePython(opts) {
  if (opts.python) return opts.python;
  const venvBin = isWin
    ? path.join(ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venvBin)) return venvBin;
  console.warn(`未找到 .venv 内的 python(${venvBin})，回退到 PATH 中的 ${isWin ? 'python' : 'python3'}`);
  return isWin ? 'python' : 'python3';
}

function readPyVersion() {
  const cfg = path.join(ROOT, '.venv', 'pyvenv.cfg');
  try {
    const m = fs.readFileSync(cfg, 'utf8').match(/^version\s*=\s*(.+)$/m);
    if (m) return m[1].trim();
  } catch (_) {}
  return 'unknown';
}

function humanSize(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}

function dirSize(dir) {
  let total = 0;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) total += dirSize(p);
    else total += fs.statSync(p).size;
  }
  return total;
}

// 仅含 sdist 的包在下载/安装时需要构建 wheel，会启用隔离构建环境并自动安装
// 最新版 setuptools；而 setuptools>=81 已移除 pkg_resources，旧包(如 openai-whisper)
// 的 setup.py 仍 `import pkg_resources` 会报 ModuleNotFoundError。
// 这里把构建期 setuptools 钉到 <81（仍自带 pkg_resources）。PIP_CONSTRAINT 会同时
// 作用于隔离构建环境，是官方推荐的钉构建依赖方式。
const BUILD_CONSTRAINTS = 'setuptools<81\nwheel\n';

// 用带构建约束的环境执行 pip
function pipEnv(constraintsPath) {
  return { ...process.env, PIP_CONSTRAINT: constraintsPath };
}

// 下载某个 lock 的全部包到 destDir
function downloadPackages(python, lockFile, destDir, constraintsPath) {
  fs.mkdirSync(destDir, { recursive: true });
  // --no-deps: lock 已是完整解析结果，逐条下载即可，避免 pip 重新解析拉到不同版本
  // --prefer-binary: 优先 wheel，减少 sdist 触发的本地构建
  const args = [
    '-m', 'pip', 'download',
    '-r', lockFile,
    '-d', destDir,
    '--no-deps',
    '--prefer-binary',
  ];
  console.log(`\n> ${python} ${args.join(' ')}`);
  const res = spawnSync(python, args, { stdio: 'inherit', env: pipEnv(constraintsPath) });
  if (res.error) throw res.error;
  if (res.status !== 0) throw new Error(`pip download 退出码 ${res.status}`);

  // 额外把构建后端(setuptools<81 + wheel)也下到包目录，保证离线机器构建 sdist 时可用
  const backendArgs = [
    '-m', 'pip', 'download',
    'setuptools<81', 'wheel',
    '-d', destDir,
    '--prefer-binary',
  ];
  console.log(`\n> ${python} ${backendArgs.join(' ')}`);
  const res2 = spawnSync(python, backendArgs, { stdio: 'inherit', env: pipEnv(constraintsPath) });
  if (res2.error) throw res2.error;
  if (res2.status !== 0) throw new Error(`pip download(构建后端) 退出码 ${res2.status}`);
}

// 生成离线安装辅助脚本与说明
function writeInstallHelpers(stagingDir, target) {
  const lockName = `${target}.lock`;

  const cmd = `@echo off
rem ${target} 离线安装包。把本目录(packages)作为唯一来源安装，全程不联网。
setlocal
set HERE=%~dp0
rem 钉构建期 setuptools<81，避免老 sdist 因新 setuptools 缺 pkg_resources 而构建失败
set PIP_CONSTRAINT=%HERE%constraints.txt
pip install --no-index --find-links "%HERE%packages" -r "%HERE%${lockName}"
if errorlevel 1 (
  echo.
  echo 安装失败。可改用指定的 python，例如:
  echo   "C:\\path\\to\\python.exe" -m pip install --no-index --find-links "%HERE%packages" -r "%HERE%${lockName}"
  exit /b 1
)
echo 离线安装完成。
`;

  const sh = `#!/bin/bash
# ${target} 离线安装包。把本目录(packages)作为唯一来源安装，全程不联网。
set -e
HERE="$(cd "$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PYTHON="\${PYTHON:-python3}"
# 钉构建期 setuptools<81，避免老 sdist 因新 setuptools 缺 pkg_resources 而构建失败
export PIP_CONSTRAINT="$HERE/constraints.txt"
"$PYTHON" -m pip install --no-index --find-links "$HERE/packages" -r "$HERE/${lockName}"
echo "离线安装完成。"
`;

  const readme = `# ${target} 离线安装包

本包由 dependencies/pack_offline.cjs 生成，内含 ${lockName} 锁定的全部
Python 依赖(wheel / sdist)。适用于无网络或网络受限的机器。

外层 .pkg 实为 tar.gz，可用 tar 解压(Win10+/macOS/Linux 均自带):
  tar -xf ${target}-offline-installer.pkg
SSUI 桌面端可在安装界面直接选择 .pkg，自动解压并离线安装。

## 目录结构
- packages/            所有已下载的依赖包(含构建后端 setuptools/wheel)
- python/              对应平台的 Python 解释器(python-build-standalone, 可选)
- ${lockName}          锁文件(安装时作为 -r 输入)
- constraints.txt      构建约束(钉 setuptools<81，保留 pkg_resources)
- install-offline.cmd  Windows 一键安装
- install-offline.sh   Linux/macOS 一键安装
- manifest.json        生成信息

## 安装(任选其一)
1) 直接运行对应平台脚本:
   Windows:        install-offline.cmd
   Linux/macOS:    bash install-offline.sh

2) 手动执行(注意先设置构建约束):
   Windows:     set PIP_CONSTRAINT=%CD%\\constraints.txt
   Linux/macOS: export PIP_CONSTRAINT="$PWD/constraints.txt"
   然后:        pip install --no-index --find-links packages -r ${lockName}

注意: 离线机器的操作系统与 Python 版本需与打包时一致，否则 wheel 不兼容。
`;

  fs.writeFileSync(path.join(stagingDir, 'install-offline.cmd'), cmd.replace(/\n/g, '\r\n'), 'utf8');
  const shPath = path.join(stagingDir, 'install-offline.sh');
  fs.writeFileSync(shPath, sh, 'utf8');
  try { fs.chmodSync(shPath, 0o755); } catch (_) {}
  fs.writeFileSync(path.join(stagingDir, 'README.txt'), readme, 'utf8');
}

// 下载目标平台对应的 Python(python-build-standalone)到 destDir。
// 该压缩包与平台无关地可下载（只是按 arch 取不同文件），因此可在任意机器上为任意目标打包。
// 返回下载到的文件名；无对应架构时返回 null。
function downloadPythonStandalone(target, destDir) {
  const arch = TARGET_ARCH[target];
  if (!arch) {
    console.warn(`目标 ${target} 无对应的 Python 架构映射，跳过 Python 打包`);
    return null;
  }
  fs.mkdirSync(destDir, { recursive: true });

  const fileName = `cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-${arch}-install_only_stripped.tar.gz`;
  const outFile = path.join(destDir, fileName);
  const githubUrl = `https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE}/${fileName}`;
  // Gitee 镜像用 % 代替文件名中的 +（与后端 download_python 一致）
  const giteeUrl = `https://gitee.com/Swordtooth/ssui_assets/releases/download/v0.0.2/cpython-${PYTHON_VERSION}%${PYTHON_RELEASE}-${arch}-install_only_stripped.tar.gz`;

  const curlArgs = (url) => {
    const a = ['-fL'];
    if (isWin) a.push('--ssl-revoke-best-effort');
    a.push(url, '-o', outFile);
    return a;
  };

  console.log(`\n下载 Python(${arch}): ${githubUrl}`);
  let res = spawnSync('curl', curlArgs(githubUrl), { stdio: 'inherit' });
  if (res.error) throw res.error;
  if (res.status !== 0) {
    console.warn('GitHub 下载失败，尝试 Gitee 镜像...');
    res = spawnSync('curl', curlArgs(giteeUrl), { stdio: 'inherit' });
    if (res.error) throw res.error;
    if (res.status !== 0) throw new Error(`Python 下载失败(curl 退出码 ${res.status})`);
  }
  return fileName;
}

// 把 stagingDir 的内容打包成 outFile(.pkg，内容为 tar.gz)
// 用 tar.gz 而非 zip：桌面端 unpack_app(flate2+tar)可直接解压复用，且 tar 在
// Win10+/macOS/Linux 均自带，无 PowerShell Compress-Archive 的 2GB 流限制。
function createPkg(stagingDir, outFile) {
  fs.rmSync(outFile, { force: true });
  console.log('正在用 tar 打包(tar.gz 格式)...');
  const res = spawnSync('tar', ['-czf', outFile, '-C', stagingDir, '.'], { stdio: 'inherit' });
  if (res.error) throw res.error;
  if (res.status !== 0) throw new Error(`tar 退出码 ${res.status}`);
}

function packOne(target, lockFile, opts, python, pyVersion) {
  console.log(`\n========== 处理目标: ${target} ==========`);
  const stagingDir = path.join(opts.outputDir, `${target}-offline-installer`);
  const packagesDir = path.join(stagingDir, 'packages');

  fs.rmSync(stagingDir, { recursive: true, force: true });
  fs.mkdirSync(stagingDir, { recursive: true });

  // 写入构建约束文件（下载与离线安装共用），钉 setuptools<81 以保留 pkg_resources
  const constraintsPath = path.join(stagingDir, 'constraints.txt');
  fs.writeFileSync(constraintsPath, BUILD_CONSTRAINTS, 'utf8');

  downloadPackages(python, lockFile, packagesDir, constraintsPath);

  const fileCount = fs.readdirSync(packagesDir).length;
  if (fileCount === 0) throw new Error(`没有下载到任何包(${packagesDir} 为空)`);

  // 拷贝锁文件供离线安装使用
  fs.copyFileSync(lockFile, path.join(stagingDir, `${target}.lock`));

  // 下载并附带对应平台的 Python 解释器（python-build-standalone）
  let pythonArchive = null;
  if (!opts.noPython) {
    pythonArchive = downloadPythonStandalone(target, path.join(stagingDir, 'python'));
  }

  // 写入辅助脚本与说明
  writeInstallHelpers(stagingDir, target);

  // 写 manifest
  const manifest = {
    target,
    python: pyVersion,
    pythonVersion: PYTHON_VERSION,
    pythonRelease: PYTHON_RELEASE,
    pythonArchive,
    packageCount: fileCount,
    builtOn: process.platform,
    createdAt: new Date().toISOString(),
    installCommand: `pip install --no-index --find-links packages -r ${target}.lock`,
  };
  fs.writeFileSync(path.join(stagingDir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');

  const stagedSize = humanSize(dirSize(stagingDir));
  const outFile = path.join(opts.outputDir, `${target}-offline-installer.pkg`);
  console.log(`已下载 ${fileCount} 个包(展开 ${stagedSize})，开始打包...`);
  createPkg(stagingDir, outFile);

  if (!opts.keepStaging) {
    fs.rmSync(stagingDir, { recursive: true, force: true });
  }

  const size = humanSize(fs.statSync(outFile).size);
  console.log(`完成: ${outFile}（${size}）`);
  return { target, outFile, fileCount, size };
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) { printHelp(); return; }

  const targets = resolveTargets(opts);
  if (targets.length === 0) {
    console.error('没有可处理的 lock 文件。请用 --target 指定，或先运行 `yarn update-lock` 生成。');
    process.exit(1);
  }

  const python = resolvePython(opts);
  const pyVersion = readPyVersion();
  fs.mkdirSync(opts.outputDir, { recursive: true });

  console.log(`下载用 Python: ${python}（版本 ${pyVersion}）`);
  console.log(`输出目录: ${opts.outputDir}`);
  console.log(`待处理目标: ${targets.map(t => t.target).join(', ')}`);

  const results = [];
  const start = Date.now();
  for (const { target, lockFile } of targets) {
    try {
      results.push(packOne(target, lockFile, opts, python, pyVersion));
    } catch (e) {
      console.error(`目标 ${target} 打包失败: ${e.message}`);
      process.exitCode = 1;
    }
  }

  const secs = ((Date.now() - start) / 1000).toFixed(0);
  console.log(`\n===== 全部完成（耗时 ${secs}s）=====`);
  for (const r of results) {
    console.log(`  ${r.target}: ${r.outFile}（${r.fileCount} 个包, ${r.size}）`);
  }
}

main();
