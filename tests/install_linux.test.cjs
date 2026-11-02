const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const python = path.join(root, '.venv/bin/python');

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(root, '.build/tmp/install with spaces-'));
  t.after(() => fs.rmSync(dir, {recursive: true, force: true}));
  fs.mkdirSync(path.join(dir, 'dependencies'));
  return dir;
}

test('HTTP errors stop bootstrap before publishing Python', {skip: process.platform !== 'linux'}, t => {
  const dir = fixture(t);
  fs.copyFileSync(path.join(root, 'dependencies/install.sh'), path.join(dir, 'dependencies/install.sh'));
  const bin = path.join(dir, 'fakebin'); fs.mkdirSync(bin);
  fs.writeFileSync(path.join(bin, 'curl'), '#!/bin/sh\nexit 22\n', {mode: 0o755});
  const result = spawnSync('bash', [path.join(dir, 'dependencies/install.sh')], {
    env: {...process.env, PATH: bin + ':' + process.env.PATH}, encoding: 'utf8'
  });
  assert.equal(result.status, 22);
  assert.equal(fs.existsSync(path.join(dir, '.venv/bin/python')), false);
  assert.deepEqual(fs.readdirSync(path.join(dir, '.venv')), []);
});

test('runtime launch preserves arguments, native environment and exit code', {skip: process.platform !== 'linux'}, t => {
  const dir = fixture(t);
  const prefix = path.join(dir, 'compiler prefix'); fs.mkdirSync(path.join(prefix, 'bin'), {recursive: true});
  fs.writeFileSync(path.join(prefix, 'bin/nvcc'), '');
  const marker = path.join(dir, '.venv/native-cuda'); fs.mkdirSync(marker, {recursive: true});
  fs.writeFileSync(path.join(marker, 'runtime.json'), JSON.stringify({prefix}));
  const result = spawnSync(python, [path.join(root, 'dependencies/native_cuda.py'), '--root', dir,
    'exec', '--', python, '-c', 'import os,sys,json; print(json.dumps([sys.argv[1:],os.environ["CUDA_HOME"],os.environ["CXX"]])); sys.exit(17)', 'argument with spaces', '$(literal)'], {encoding:'utf8'});
  assert.equal(result.status, 17, result.stderr);
  const [args, cuda, cxx] = JSON.parse(result.stdout);
  assert.deepEqual(args, ['argument with spaces', '$(literal)']);
  assert.equal(cuda, prefix);
  assert.equal(cxx, path.join(prefix, 'bin/x86_64-conda-linux-gnu-c++'));
});

test('base Python launch works without CUDA and does not install anything', {skip: process.platform !== 'linux'}, t => {
  const dir = fixture(t);
  const result = spawnSync(python, [path.join(root, 'dependencies/native_cuda.py'), '--root', dir,
    'exec', '--', python, '-c', 'print("BASE_LAUNCH_OK")'], {encoding:'utf8'});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), 'BASE_LAUNCH_OK');
  assert.equal(fs.existsSync(path.join(dir, '.venv')), false);
});

test('fresh Linux bootstrap installs runnable Python and uv', {
  skip: process.platform !== 'linux' || process.env.SSUI_RUN_INSTALL_TESTS !== '1', timeout: 240000
}, t => {
  const dir = fixture(t);
  fs.copyFileSync(path.join(root, 'dependencies/install.sh'), path.join(dir, 'dependencies/install.sh'));
  const result = spawnSync('bash', [path.join(dir, 'dependencies/install.sh')], {
    env: {...process.env, TMPDIR: path.join(root, '.build/tmp')}, encoding:'utf8', timeout: 210000
  });
  assert.equal(result.status, 0, result.stderr);
  const py = path.join(dir, '.venv/bin/python');
  const probe = spawnSync(py, ['-c', 'import sys,packaging; assert sys.version_info[:3]==(3,12,8); assert packaging.__version__=="24.1"'], {encoding:'utf8'});
  assert.equal(probe.status, 0, probe.stderr);
  assert.equal(spawnSync(path.join(dir, '.venv/bin/uv'), ['--version']).status, 0);
});

test('Python launch aliases whitespace venv paths without moving user files', {skip:process.platform!=='linux'},t=>{
  const dir=fixture(t);
  const venv=path.join(dir,'.venv');
  const created=spawnSync(python,['-m','venv',venv],{encoding:'utf8'});
  assert.equal(created.status,0,created.stderr);
  const result=spawnSync(path.join(venv,'bin/python'),[path.join(root,'dependencies/native_cuda.py'),'--root',dir,'exec','--',path.join(venv,'bin/python'),'-c','import sys; print(sys.executable); print(sys.argv[1])','unchanged argument'],{env:{...process.env,XDG_CACHE_HOME:path.join(root,'.build/cache')},encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const [executable,arg]=result.stdout.trim().split('\n');
  assert.equal(/\s/.test(executable),false);
  assert.equal(arg,'unchanged argument');
});

test('repair command remains runnable when the managed compiler was deleted', {skip:process.platform!=='linux'},t=>{
  const dir=fixture(t);
  const marker=path.join(dir,'.venv/native-cuda');fs.mkdirSync(marker,{recursive:true});
  fs.writeFileSync(path.join(marker,'runtime.json'),JSON.stringify({prefix:path.join(dir,'deleted compiler')}));
  const repair=path.join(dir,'dependencies/native_cuda.py');fs.writeFileSync(repair,'print("REPAIR_REACHED")');
  const result=spawnSync(python,[path.join(root,'dependencies/native_cuda.py'),'--root',dir,'exec','--',python,repair,'install'],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  assert.equal(result.stdout.trim(),'REPAIR_REACHED');
});

test('missing optional native compiler does not block base Python commands', {skip:process.platform!=='linux'},t=>{
  const dir=fixture(t), marker=path.join(dir,'.venv/native-cuda');fs.mkdirSync(marker,{recursive:true});
  fs.writeFileSync(path.join(marker,'runtime.json'),JSON.stringify({prefix:path.join(dir,'missing')}));
  const result=spawnSync(python,[path.join(root,'dependencies/native_cuda.py'),'--root',dir,'exec','--',python,'-c','print("BASE_STILL_WORKS")'],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  assert.equal(result.stdout.trim(),'BASE_STILL_WORKS');
  assert.match(result.stderr,/compiler is missing/);
});
