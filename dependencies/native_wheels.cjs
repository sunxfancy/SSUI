// Locally built Intel macOS wheels are verified before installation or bundling.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { getRuntime } = require('./runtime.cjs');
const expected = {
  torch: ['2.8.0+ssui.cpu', 'ba56102387ef21a3b04b357e5b183d48f0afefc7'],
  torchvision: ['0.23.0+ssui.cpu', '824e8c8726b65fd9d5abdc9702f81c2b0c4c0dc8'],
  torchaudio: ['2.8.0+ssui.cpu', '6e1c7fe9ff6d82b8665d0a46d859d3357d2ebaaa'],
};
function verifyWheelhouse(directory) {
  const root = path.resolve(directory);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
  if (manifest.target !== 'macos-x86_64' || manifest.python !== getRuntime('darwin', 'x64').pythonVersion) {
    throw new Error('Native wheel runtime does not match Intel macOS');
  }
  if (manifest.wheels.length !== 3 || new Set(manifest.wheels.map(w => w.name)).size !== 3) {
    throw new Error('Expected exactly three native PyTorch wheels');
  }
  const listed = new Set(manifest.wheels.map(w => w.filename));
  if (fs.readdirSync(root).some(name => name.endsWith('.whl') && !listed.has(name))) {
    throw new Error('Unlisted wheel in native wheel directory');
  }
  for (const wheel of manifest.wheels) {
    const pin = expected[wheel.name];
    if (!pin || wheel.version !== pin[0] || wheel.source !== pin[1]) throw new Error('Native wheel source/version mismatch');
    if (path.basename(wheel.filename) !== wheel.filename || wheel.filename.includes('\\') ||
        !wheel.filename.startsWith(`${wheel.name}-${wheel.version}-`) ||
        !/-cp312-cp312-macosx_\d+_\d+_x86_64\.whl$/.test(wheel.filename)) throw new Error('Invalid native wheel filename/tag');
    const hash = crypto.createHash('sha256').update(fs.readFileSync(path.join(root, wheel.filename))).digest('hex');
    if (hash !== wheel.sha256) throw new Error('Native wheel checksum mismatch');
  }
  return manifest;
}
function wheelhouseFor(target, env = process.env) {
  if (target !== 'macosx-x86_64') return null;
  if (!env.SSUI_NATIVE_WHEELHOUSE) throw new Error('Intel macOS requires SSUI_NATIVE_WHEELHOUSE: download the verified macos-intel-wheels workflow artifact first');
  const directory = path.resolve(env.SSUI_NATIVE_WHEELHOUSE);
  verifyWheelhouse(directory);
  return directory;
}
module.exports = { verifyWheelhouse, wheelhouseFor, expected };
if (require.main === module) {
  verifyWheelhouse(process.argv[2]);
  console.log('Verified native Intel macOS wheel sources, versions, tags and hashes');
}
