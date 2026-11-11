const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');
const { getRuntimeTarget } = require('./platform.cjs');
const { dependencyProfile } = require('./runtime_target.cjs');
const { resolveDependencies } = require('./dependency_config.cjs');

// Preserve PEP 440 constraints, extras and URLs. pip/uv computes intersections.
function extensionRequirements(extensionsDir) {
  if (!fs.existsSync(extensionsDir)) return [];
  const requirements = [];
  for (const entry of fs.readdirSync(extensionsDir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name, 'en'))) {
    if (!entry.isDirectory()) continue;
    const filename = path.join(extensionsDir, entry.name, 'ssextension.yaml');
    if (!fs.existsSync(filename)) continue;
    const config = yaml.load(fs.readFileSync(filename, 'utf8'));
    const dependencies = config?.server?.dependencies;
    if (dependencies === undefined) continue;
    if (!Array.isArray(dependencies) || dependencies.some(v => typeof v !== 'string' || !v.trim() || /[\r\n]/.test(v) || v.trim().startsWith('-'))) {
      throw new Error('Invalid extension dependencies: ' + filename);
    }
    requirements.push(...dependencies.map(v => v.trim()));
  }
  return [...new Set(requirements)];
}

function main() {
  const target = getRuntimeTarget();
  dependencyProfile(target);
  const resolved = resolveDependencies(target);
  const root = path.resolve(__dirname, '..');
  const outputPath = path.join(root, '.build', 'requirements.txt');
  const lines = [...new Set([...resolved.requirements, ...extensionRequirements(path.join(root, 'extensions'))])];
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, '# Generated from dependencies/dependencies.yaml and extension manifests. DO NOT EDIT.\n'
    + [...lines, ...resolved.extraIndexes.map(url => '--extra-index-url ' + url)].join('\n') + '\n');
  console.log('Generated: ' + outputPath);
}

if (require.main === module) {
  try { main(); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}

module.exports = { extensionRequirements, main };
