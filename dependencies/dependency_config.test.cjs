const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { config, profileFromName } = require('./runtime_target.cjs');
const { loadConfig, validateConfig, resolveDependencies, renderRequirements, generateRequirements } = require('./dependency_config.cjs');
const { extensionRequirements } = require('./combine_requirements.cjs');
const { parseArgs, compileArgs, parseLockFile } = require('./update_lock.cjs');
const { main: generate } = require('./generate_requirements.cjs');

function sample() {
  return {
    version: 1,
    common: { packages: { 'Demo[base]': '>=1,<5', remove_me: '>=1', unchanged: '>=1' }, extraIndexes: ['https://example.com/simple'] },
    os: { windows: { packages: { 'demo[os]': '>=2' } }, linux: {}, macos: {} },
    arch: { arm64: { packages: { 'DEMO[arm]': '>=3', remove_me: null } }, x64: {} },
    backend: { cpu: { packages: { demo: '==4' } }, cuda: {}, rocm: {}, mps: {}, qnn: {} },
    overrides: [
      { when: { os: ['windows', 'linux'], arch: 'arm64', backend: 'cpu' }, packages: { demo: ['>=4', '<5'] }, extraIndexes: ['https://example.com/simple', 'https://example.org/simple'] },
      { when: { os: 'windows', arch: 'arm64', backend: 'qnn' }, packages: { wrong: '==1' } }
    ]
  };
}

test('OS, arch and backend compose in order; overrides replace, null removes, indexes deduplicate', () => {
  const result = resolveDependencies({ os: 'windows', arch: 'arm64', backend: 'cpu' }, sample());
  assert.deepEqual(result.requirements, ['demo>=4', 'demo<5', 'unchanged>=1']);
  assert.deepEqual(result.extraIndexes, ['https://example.com/simple', 'https://example.org/simple']);
  const linux = resolveDependencies({ os: 'linux', arch: 'x64', backend: 'cuda' }, sample());
  assert.ok(linux.requirements.includes('Demo[base]>=1,<5'));
  assert.ok(linux.requirements.includes('remove_me>=1'));
  assert.ok(!linux.requirements.some(line => line.startsWith('wrong')));
});

test('CPU architecture layers apply independently on all OSes', () => {
  const spec = sample();
  spec.overrides = [];
  for (const os of config.oses) {
    const resolved = resolveDependencies({ os, arch: 'arm64', backend: 'cuda' }, spec);
    assert.ok(resolved.requirements.includes('DEMO[arm]>=3'));
    assert.ok(!resolved.requirements.some(line => line.startsWith('remove_me')));
  }
});

test('configuration rejects misspelled dimensions, invalid selections and malformed requirements', () => {
  for (const mutate of [
    s => { s.arch.amr64 = {}; },
    s => { s.overrides[0].when.arch = 'amr64'; },
    s => { s.overrides[0].when.accelerator = 'cpu'; },
    s => { s.overrides[0].when = {}; },
    s => { s.common.packages.demo = '>=1\n--index-url bad'; },
    s => { s.common.packages['Demo[second]'] = '>=1'; },
    s => { s.common.extraIndexes = ['file:///tmp/index']; },
    s => { s.common.packages.demo = []; },
    s => { s.version = 2; }
  ]) {
    const spec = sample();
    mutate(spec);
    assert.throws(() => validateConfig(spec));
  }
});

test('legacy names and full three-dimensional names generate identical requirements', () => {
  const spec = loadConfig();
  for (const target of config.profiles) {
    assert.equal(renderRequirements(profileFromName(target.dependencyTarget), spec), renderRequirements(target, spec));
    assert.doesNotThrow(() => generateRequirements(target.dependencyTarget, { check: true, spec }));
  }
});

test('migration retains OS/backend-specific versions, URLs, extras and multiple constraints', () => {
  const windows = resolveDependencies(profileFromName('windows'));
  const rocm = resolveDependencies(profileFromName('windows-amdgpu'));
  const macos = resolveDependencies(profileFromName('macosx'));
  assert.ok(windows.requirements.includes('transformers>=4.54,<4.56'));
  assert.ok(windows.requirements.includes('scipy>=1.15.2'));
  assert.ok(windows.requirements.includes('scipy>=1.15'));
  assert.ok(windows.requirements.includes('diffusers[torch]>=0.37.0,<0.41'));
  assert.ok(rocm.requirements.some(r => r.startsWith('torch @ https://repo.radeon.com/')));
  assert.ok(rocm.requirements.includes('tokenizers==0.22.2'));
  assert.ok(rocm.requirements.includes('transformers==4.57.6'));
  assert.ok(macos.requirements.includes('torch==2.4.1'));
  assert.ok(!macos.requirements.some(r => r.includes('win_amd64')));
  assert.ok(!macos.requirements.some(r => r.startsWith('xatlas')));
});

test('generation fails for missing dependency support instead of producing an ARM/CUDA fallback', () => {
  assert.throws(() => generateRequirements('linux-arm64-qnn'), /尚未提供/);
  assert.throws(() => generate(['--target']), /缺少/);
  assert.throws(() => generate(['--typo']), /未知/);
  const spec = sample();
  delete spec.backend.qnn;
  assert.throws(() => resolveDependencies({ os: 'windows', arch: 'arm64', backend: 'qnn' }, spec), /尚未声明/);
});

test('stale generated requirements are detected', () => {
  const spec = loadConfig();
  spec.common.packages['new-package'] = '==1.0';
  assert.throws(() => generateRequirements('windows', { check: true, spec }), /已过期/);
});

test('extension compound version constraints are passed intact to the Python resolver', () => {
  const requirements = extensionRequirements(path.join(__dirname, '..', 'extensions'));
  assert.ok(requirements.includes('diffusers>=0.37.0,<0.41'));
  assert.ok(requirements.includes('transformers>=4.51.3,<5'));
});

test('lock compilation uses the requested target, Python version and unchanged lock name', () => {
  assert.deepEqual(parseArgs(['--target', 'macos-arm64-mps', '-n']), { targets: ['macosx'], all: false, noUpgrade: true });
  assert.throws(() => parseArgs(['--target', 'windows', '--all']), /不能/);
  assert.throws(() => parseArgs(['--target']), /缺少/);
  assert.throws(() => parseArgs(['--target', 'linux-arm64-qnn']), /尚未提供/);
  const args = compileArgs('macosx', 'in file.txt', 'macosx.lock', true);
  assert.equal(args[args.indexOf('--python-platform') + 1], 'aarch64-apple-darwin');
  assert.equal(args[args.indexOf('--python-version') + 1], config.python.version);
  assert.ok(args.includes('in file.txt'));
  assert.ok(!args.includes('--upgrade'));
  assert.ok(!args.includes('--no-upgrade'));
  assert.ok(compileArgs('windows', 'in.txt', 'out.lock').includes('--upgrade'));
  const arm = compileArgs('windows-arm64-cpu', 'in.txt', 'out.lock');
  assert.equal(arm[arm.indexOf('--python-platform') + 1], 'aarch64-pc-windows-msvc');
  assert.equal(arm[arm.indexOf('--python-version') + 1], '3.12.15');
  assert.ok(arm.includes('--no-build'));
});

test('Windows ARM64 CPU uses published native wheels without cv2 collisions or GPU dependencies', () => {
  const resolved = resolveDependencies(profileFromName('windows-arm64-cpu'));
  assert.ok(resolved.requirements.includes('torch==2.9.1+cpu'));
  assert.ok(resolved.requirements.includes('WeTextProcessing==1.0.4+ssui.cpu.import1.be4d2d5c7bc86'));
  assert.ok(!resolved.requirements.some(line => line.includes('pynini-2.1.6.post1/releases')));
  assert.ok(resolved.requirements.includes('torchvision==0.24.1+d801a34'));
  assert.ok(resolved.requirements.includes('sentencepiece==0.2.2'));
  assert.ok(resolved.requirements.includes('transformers==4.57.6'));
  assert.ok(resolved.requirements.includes('imageio[ffmpeg]>=2.37.0'));
  for (const name of ['opencv-contrib-python', 'xformers', 'cupy-cuda12x', 'bitsandbytes', 'xatlas']) {
    assert.ok(!resolved.requirements.some(line => line.toLowerCase().startsWith(name.toLowerCase())), name);
  }
  for (const name of ['torchaudio', 'tiktoken', 'opencv-python-headless', 'pyworld', 'pymeshfix', 'pyarrow', 'moderngl', 'openai-whisper', 'pynini', 'soxr', 'hf-transfer', 'vtk', 'mediapipe', 'imageio-ffmpeg', 'transformers_stream_generator', 'controlnet-aux']) {
    assert.ok(resolved.requirements.some(line => line.startsWith(name + '==') && line.includes('+ssui.')), name);
  }
  assert.ok(resolved.requirements.includes('numba==0.68.0'));
  assert.ok(resolved.requirements.includes('llvmlite==0.50.0'));
  assert.ok(resolved.requirements.includes('librosa==0.11.0'));
  assert.ok(resolved.requirements.includes('soundfile==0.14.0'));
  assert.ok(resolved.requirements.includes('setuptools==80.9.0'));
  assert.ok(resolved.extraIndexes.includes('https://sunxfancy.github.io/ssui-python-packages/simple/windows/arm64/cpu/2.9.1/'));
  assert.ok(!resolved.requirements.some(line => /win_amd64|cu124/.test(line)));
  const fs = require('node:fs');
  const lock = fs.readFileSync(path.join(__dirname, 'windows-arm64-cpu.lock'), 'utf8');
  assert.ok(!/win_amd64|cu124/.test(lock));
  assert.match(lock, /--python-platform aarch64-pc-windows-msvc/);
  assert.match(lock, /--no-build/);
  assert.ok(!/^(?:opencv-contrib-python|opencv-python)==/m.test(lock));
  assert.match(lock, /^imageio-ffmpeg==0\.6\.0\+ssui\./m);
  assert.match(lock, /^mediapipe==1\.1\.1\+ssui\./m);
  assert.match(lock, /^transformers-stream-generator==0\.0\.4\+ssui\./m);
  assert.match(lock, /^vtk==9\.4\.2\+ssui\./m);
});

test('lock graph retains direct wheel URLs and their following dependency edges', () => {
  const url = 'https://example.com/WeTextProcessing-1.0.4-py3-none-any.whl#sha256=abc';
  const parsed = parseLockFile(`numpy==2.5.4\n    # via demo\nwetextprocessing @ ${url}\n    # via -r dependencies/requirements-windows-arm64-cpu.txt\nwrapt==2.5.1\n    # via wetextprocessing\n`);
  assert.deepEqual(parsed.numpy.dependents, ['demo']);
  assert.equal(parsed.wetextprocessing.version, '1.0.4');
  assert.equal(parsed.wetextprocessing.url, url);
  assert.equal(parsed.wetextprocessing.isRoot, true);
  assert.deepEqual(parsed.wrapt.dependents, ['wetextprocessing']);
});

test('generated lock graph preserves uv root and reverse-dependency annotations', () => {
  const parsed = parseLockFile('# uv header\naccelerate==1.15.0\n    # via\n    #   -r dependencies/requirements-windows-arm64-cpu.txt\n    #   diffusers\nnumpy==2.0.0\n    # via accelerate\n--extra-index-url https://download.pytorch.org/whl/cpu\n');
  assert.equal(parsed.accelerate.isRoot, true);
  assert.deepEqual(parsed.accelerate.dependents, ['diffusers']);
  assert.deepEqual(parsed.numpy.dependents, ['accelerate']);
});

 test('Windows ROCm pins validated native wheels with hashes without changing CUDA', () => {
  const amd = resolveDependencies(profileFromName('windows-amdgpu'));
  for (const name of ['cumesh', 'nvdiffrast', 'natten']) {
    const requirement = amd.requirements.find(line => line.startsWith(name + ' @ '));
    assert.match(requirement, /SSUI\/releases\/download\/rocm-wheels-20261027\//);
    assert.match(requirement, /%2Bssui\.rocm72-cp312-cp312-win_amd64\.whl#sha256=[a-f0-9]{64}$/);
  }
  const cuda = resolveDependencies(profileFromName('windows'));
  assert.ok(cuda.requirements.some(line => line.startsWith('nvdiffrast @ ') && line.includes('/v0.3.3.1/')));
  assert.ok(!cuda.requirements.some(line => line.startsWith('natten ')));
});
