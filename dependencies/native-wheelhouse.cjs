const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const runtime = require('./runtime.json');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function validateNativeWheelhouse(directory) {
  if (!directory) throw new Error('Set SSUI_NATIVE_WHEELHOUSE to the validated windows-arm64-wheels artifact directory.');
  const root = path.resolve(directory);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
  if (manifest.architecture !== 'win-arm64' || manifest.python !== runtime.pythonVersion) throw new Error('Native wheelhouse runtime mismatch');
  if (manifest.lock_sha256 !== hash(path.join(__dirname, 'windows-arm64.lock'))) throw new Error('Native wheelhouse dependency lock mismatch');
  const lock = path.join(root, 'runtime.lock');
  if (manifest.runtime_lock_sha256 !== hash(lock)) throw new Error('Native wheelhouse runtime lock checksum mismatch');
  const directoryFiles = fs.readdirSync(path.join(root, 'wheelhouse')).filter(n => n.endsWith('.whl')).sort();
  const files = Object.keys(manifest.wheels).sort();
  if (!files.length || JSON.stringify(files) !== JSON.stringify(directoryFiles)) throw new Error('Native wheelhouse inventory mismatch');
  for (const name of files) {
    if (path.basename(name) !== name || /[\\/]/.test(name) || !name.endsWith('.whl')) throw new Error('Invalid wheel filename');
    if (hash(path.join(root, 'wheelhouse', name)) !== manifest.wheels[name]) throw new Error(`Native wheel checksum mismatch: ${name}`);
  }
  const bundled = fs.readdirSync(path.join(root, 'bundled')).filter(n => n.endsWith('.whl'));
  if (!bundled.length) throw new Error('No source-built wheels to bundle');
  for (const name of bundled) {
    if (hash(path.join(root, 'bundled', name)) !== manifest.wheels[name]) throw new Error(`Bundled wheel checksum mismatch: ${name}`);
  }
  return { root, manifest, lock, files, bundled };
}
module.exports = { validateNativeWheelhouse };
