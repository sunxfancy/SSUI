// Shared root/CI entry point; keep native prerequisites outside Python's
// isolated package build environments and preserve their locked versions.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { resolveConfig, executable } = require('./dev_config.cjs');

function prepare({ env = process.env, platform = process.platform, arch = process.arch } = {}) {
  if (platform === 'darwin') return require('./macos_prerequisites.cjs').prepare({ env });
  if (platform !== 'linux' || arch !== 'arm64') return { ...env };
  const prefix = path.resolve(__dirname, '../.build/native/openfst-1.8.4');
  const result = execFileSync(executable('python', env), [
    path.join(__dirname, 'prepare_openfst.py'), '--prefix', prefix,
  ], { encoding: 'utf8', env, stdio: ['ignore', 'pipe', 'inherit'] });
  return { ...env, ...JSON.parse(result) };
}

if (require.main === module) {
  const env = prepare({ env: resolveConfig() });
  if (process.argv.includes('--github-env')) {
    for (const name of ['CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'LD_LIBRARY_PATH', 'LDFLAGS']) {
      if (env[name] !== undefined) {
        if (/[\r\n]/.test(env[name])) throw new Error(`Invalid newline in ${name}`);
        fs.appendFileSync(process.env.GITHUB_ENV, `${name}=${env[name]}\n`);
      }
    }
  }
}
module.exports = { prepare };
