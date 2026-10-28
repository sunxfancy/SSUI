const { test } = require('node:test');
const assert = require('node:assert/strict');
const { config, runtimeTarget, targetName, dependencyProfile, profileFromName, pythonTriple, pythonDistribution, assertPythonRuntime, detectRuntime } = require('./runtime_target.cjs');

test('ARM64 is independent of OS and backend', () => {
  for (const os of config.oses) {
    for (const backend of config.backends) {
      const target = runtimeTarget(os, 'arm64', backend);
      assert.equal(targetName(target), `${os}-arm64-${backend}`);
      assert.match(pythonTriple(target), /^aarch64-/);
    }
  }
});

test('existing dependency names round-trip without changing their architecture', () => {
  for (const profile of config.profiles) {
    assert.deepEqual(dependencyProfile(profile), profileFromName(profile.dependencyTarget));
    assert.deepEqual(profileFromName(targetName(profile)), profile);
    assert.ok(require('node:fs').existsSync(require('node:path').join(__dirname, `${profile.dependencyTarget}.lock`)));
  }
});

test('missing ARM and QNN dependencies never fall back to x64/CUDA', () => {
  assert.throws(() => dependencyProfile(runtimeTarget('linux', 'arm64', 'cpu')), /尚未提供/);
  assert.throws(() => dependencyProfile(runtimeTarget('windows', 'arm64', 'qnn')), /尚未提供/);
  assert.equal(profileFromName('windows-arm64-cpu').experimental, true);
  assert.throws(() => runtimeTarget('windows', 'ia32', 'cpu'), /CPU/);
});

test('Windows emulation preserves host, process and requested target separately', () => {
  const env = { PROCESSOR_ARCHITECTURE: 'AMD64', PROCESSOR_ARCHITEW6432: 'ARM64' };
  const detected = detectRuntime({ os: 'win32', arch: 'x64', env });
  assert.equal(detected.hostArch, 'arm64');
  assert.equal(detected.processArch, 'x64');
  assert.equal(detected.target.arch, 'x64');
  const native = detectRuntime({ os: 'win32', arch: 'x64', env: { ...env, SSUI_TARGET_ARCH: 'arm64' } });
  assert.deepEqual(native.target, { os: 'windows', arch: 'arm64', backend: 'cpu' });
});

test('macOS MPS, AMD ROCm, native ARM CPU and explicit backend selection', () => {
  assert.equal(detectRuntime({ os: 'darwin', arch: 'arm64', env: {} }).target.backend, 'mps');
  assert.equal(detectRuntime({ os: 'linux', arch: 'x64', gpu: 'amd', env: {} }).target.backend, 'rocm');
  assert.equal(detectRuntime({ os: 'win32', arch: 'arm64', env: {} }).target.backend, 'cpu');
  assert.equal(detectRuntime({ os: 'win32', arch: 'arm64', env: { SSUI_COMPUTE_BACKEND: 'qnn' } }).target.backend, 'qnn');
  assert.throws(() => detectRuntime({ env: { SSUI_COMPUTE_BACKEND: 'invalid' } }), /后端/);
});

test('default lock generation only includes the current OS and architecture', () => {
  const { getCurrentPlatformTargets } = require('./platform.cjs');
  const original = { ...process.env };
  try {
    process.env.SSUI_TARGET_OS = 'windows';
    process.env.SSUI_TARGET_ARCH = 'arm64';
    assert.deepEqual(getCurrentPlatformTargets(), ['windows-arm64-cpu']);
    process.env.SSUI_TARGET_ARCH = 'x64';
    assert.deepEqual(getCurrentPlatformTargets(), ['windows', 'windows-amdgpu']);
  } finally {
    for (const key of ['SSUI_TARGET_OS', 'SSUI_TARGET_ARCH']) {
      if (original[key] === undefined) delete process.env[key];
      else process.env[key] = original[key];
    }
  }
});

test('Python architecture must match even when Node and Python run different architectures', () => {
  const target = runtimeTarget('windows', 'arm64', 'cpu');
  assert.throws(() => assertPythonRuntime(target, { os: 'win32', arch: 'AMD64' }), /不匹配/);
  assert.throws(() => assertPythonRuntime(target, { os: 'linux', arch: 'aarch64' }), /不匹配/);
  assert.doesNotThrow(() => assertPythonRuntime(target, { os: 'win32', arch: 'ARM64' }));
});

test('desktop and Node choose identical profiles, defaults and Python distributions', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const Module = require('node:module');
  const ts = require('typescript');
  const filename = path.join(__dirname, '../desktop/src/providers/runtimeTarget.ts');
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true }
  });
  const desktopModule = new Module(filename, module);
  desktopModule.filename = filename;
  desktopModule.paths = Module._nodeModulePaths(path.dirname(filename));
  desktopModule._compile(compiled.outputText, filename);
  const desktop = desktopModule.exports;
  for (const os of config.oses) {
    for (const arch of config.architectures) {
      for (const gpu of ['nvidia', 'amd', 'unknown']) {
        const target = detectRuntime({ os, arch, gpu, env: {} }).target;
        assert.deepEqual(desktop.makeRuntimeTarget(os, arch, gpu), target);
        if (config.profiles.some(p => p.os === target.os && p.arch === target.arch && p.backend === target.backend)) {
          assert.deepEqual(desktop.pythonDistribution(target), pythonDistribution(target));
          assert.deepEqual(desktop.dependencyProfile(target), dependencyProfile(target));
        } else {
          assert.throws(() => desktop.dependencyProfile(target), /尚未提供/);
        }
      }
    }
  }
});

test('ARM64 CPU uses an available native Python release without changing existing targets', () => {
  const arm = pythonDistribution(profileFromName('windows-arm64-cpu'));
  assert.deepEqual(arm, { version: '3.12.15', release: '20261021', triple: 'aarch64-pc-windows-msvc' });
  assert.equal(pythonDistribution(profileFromName('windows')).version, '3.12.8');
});
