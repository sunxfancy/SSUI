const config = require('./runtime.json');
function getRuntime(os = process.platform, cpu = process.arch) {
  const platform = { win32: 'windows', darwin: 'macos', linux: 'linux', windows: 'windows', macos: 'macos' }[os];
  const arch = { x64: 'x86_64', x86_64: 'x86_64', arm64: 'arm64', aarch64: 'arm64' }[cpu];
  const id = `${platform}-${arch}`;
  const target = config.targets[id];
  if (!target) throw new Error(`Unsupported 64-bit runtime: ${os}/${cpu}`);
  return { ...config, targets: undefined, ...target, id };
}
module.exports = { config, getRuntime };
if (require.main === module) {
  const runtime = getRuntime();
  if (process.argv[2] === '--github-output') {
    require('fs').appendFileSync(process.env.GITHUB_OUTPUT,
      `python=${runtime.pythonVersion}\nuv=${runtime.uvVersion}\nlock=${runtime.lockFile}\ntriple=${runtime.pythonTarget}\n`);
  } else console.log(JSON.stringify(runtime));
}
