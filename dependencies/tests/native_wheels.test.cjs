const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { expected, verifyWheelhouse, wheelhouseFor } = require('../native_wheels.cjs');
const { getRuntime } = require('../runtime.cjs');
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssui-wheels-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const wheels = Object.entries(expected).map(([name, [version, source]]) => {
    const filename = `${name}-${version}-cp312-cp312-macosx_13_0_x86_64.whl`;
    const bytes = Buffer.from(name);
    fs.writeFileSync(path.join(root, filename), bytes);
    return { name, version, source, filename, sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
  });
  const manifest = { target: 'macos-x86_64', python: getRuntime('darwin', 'x64').pythonVersion, wheels };
  const save = () => fs.writeFileSync(path.join(root, 'manifest.json'), JSON.stringify(manifest));
  save();
  return { root, manifest, save };
}
test('rejects tampering even when the wheel filename/version is unchanged', t => {
  const { root, manifest } = fixture(t);
  assert.equal(verifyWheelhouse(root).wheels.length, 3);
  fs.appendFileSync(path.join(root, manifest.wheels[0].filename), 'changed');
  assert.throws(() => verifyWheelhouse(root), /checksum/);
});
test('rejects missing packages, foreign architectures, and changed source commits', t => {
  for (const mutate of [m => m.wheels.pop(), m => m.wheels[0].source = '0'.repeat(40),
    m => m.wheels[0].filename = '../outside.whl', m => m.wheels[0].filename = m.wheels[0].filename.replace('x86_64', 'arm64'),
    m => m.python = '3.13.0']) {
    const { root, manifest, save } = fixture(t);
    mutate(manifest); save();
    assert.throws(() => verifyWheelhouse(root));
  }
});
test('Intel requires compiled wheels; other targets do not inherit them', () => {
  assert.throws(() => wheelhouseFor('macosx-x86_64', {}), /SSUI_NATIVE_WHEELHOUSE/);
  assert.equal(wheelhouseFor('windows-arm64-cpu', {}), null);
});

test('rejects unverified wheels that a package resolver could otherwise select', t => {
  const { root } = fixture(t);
  fs.writeFileSync(path.join(root, 'unexpected-1.0-py3-none-any.whl'), 'unverified');
  assert.throws(() => verifyWheelhouse(root), /Unlisted/);
});
