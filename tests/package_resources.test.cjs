const {test} = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const tar = require('tar');
const root = path.resolve(__dirname, '..');
const resources = path.join(root, 'desktop/src-tauri/resources');

test('desktop archives contain SDKs and vendored runtimes', async () => {
  for (const [name, required] of [
    ['Video', ['ssui_video/Wan21.py', 'ssui_video/Wan21Resident.py', 'ssui_video/CogVideo2B.py', 'diffsynth/__init__.py']],
    ['3D-Model', ['ssui_3dmodel/Trellis.py', 'ssui_3dmodel/ShapE.py', 'vendor/trellis/__init__.py']],
    ['Motion', ['ssui_motion/MDM.py', 'ssui_motion/mdm_runner.py']]
  ]) {
    const entries = [];
    await tar.t({file:path.join(resources, 'extensions', `${name}-0.1.0.tar.gz`), onentry: e => entries.push(e.path)});
    for (const file of required) assert.ok(entries.includes(`${name}/${file}`), `${name}/${file} missing`);
  }
});

test('Linux lock and native setup ship with the desktop package', async () => {
  const nativeFiles = ['native_cuda.py', 'native-cuda-linux.explicit.txt', 'requirements-native-cuda-linux.txt', 'requirements-motion.txt'];
  for (const file of ['linux.lock', ...nativeFiles]) {
    assert.ok(fs.statSync(path.join(resources, 'dependencies', file)).size > 0, file);
  }
  const entries=[];
  await tar.t({file:path.join(resources,'app.tar.gz'), onentry:e=>entries.push(e.path)});
  for (const file of nativeFiles) assert.ok(entries.includes('dependencies/'+file), file);
});

test('every workflow picker entry resolves to a bundled example', () => {
  const data = JSON.parse(fs.readFileSync(path.join(root,'desktop/src-tauri/workflow/data.json')));
  for (const workflow of data.officialWorkflows) {
    for (const file of workflow.fileList) {
      assert.ok(fs.statSync(path.join(root,'desktop/src-tauri/workflow/txt2img/basic',file)).isFile(), `${workflow.id}/${file}`);
    }
  }
});

test('extension manifests have no duplicate YAML keys', () => {
  const yaml = require('yaml');
  for (const name of ['Video', '3D-Model', 'Motion']) {
    yaml.parse(fs.readFileSync(path.join(root, 'extensions', name, 'ssextension.yaml'), 'utf8'), {uniqueKeys: true});
  }
});
