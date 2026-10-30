// Release defaults are projected from the existing OS / architecture / backend registry.
const { config: registry, detectRuntime, dependencyProfile, pythonDistribution } = require('./runtime_target.cjs');
function getRuntime(os = process.platform, cpu = process.arch) {
  const { target } = detectRuntime({ os, arch: cpu, env: {} });
  const profile = dependencyProfile(target);
  const python = pythonDistribution(target);
  return { id: `${target.os}-${target.arch === 'x64' ? 'x86_64' : 'arm64'}`,
    pythonVersion: python.version, pythonRelease: python.release,
    uvVersion: profile.uvVersion || registry.uvVersion,
    pythonTarget: python.triple, lockFile: `${profile.dependencyTarget}.lock` };
}
const targets = {};
for (const os of registry.oses) for (const arch of registry.architectures) {
  const runtime = getRuntime(os, arch);
  targets[runtime.id] = runtime;
}
const config = { targets };
module.exports = { config, getRuntime };
if (require.main === module) {
  const runtime = getRuntime();
  if (process.argv[2] === '--github-output') {
    require('fs').appendFileSync(process.env.GITHUB_OUTPUT,
      `python=${runtime.pythonVersion}\nuv=${runtime.uvVersion}\nlock=${runtime.lockFile}\ntriple=${runtime.pythonTarget}\n`);
  } else console.log(JSON.stringify(runtime));
}
