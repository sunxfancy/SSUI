// Pynini's macOS sdist requires OpenFst 1.8.4 with GRM headers/libraries.
// Homebrew's formula enables GRM; do not hide missing native dependencies by
// dropping Pynini or disabling build isolation.
const fs = require('node:fs');
const path = require('node:path').posix;
const { execFileSync } = require('node:child_process');

function prepare({ platform = process.platform, env = process.env,
  run = execFileSync, exists = fs.existsSync } = {}) {
  if (platform !== 'darwin') return { ...env };
  const brew = (...args) => run('brew', args, { encoding: 'utf8', env }).trim();
  let prefix;
  try { prefix = brew('--prefix', 'openfst'); }
  catch { brew('install', 'openfst'); prefix = brew('--prefix', 'openfst'); }
  // `brew --prefix` can succeed for an uninstalled formula.
  if (!exists(path.join(prefix, 'include/fst/util.h'))) {
    brew('install', 'openfst');
    prefix = brew('--prefix', 'openfst');
  }
  const versions = brew('list', '--versions', 'openfst').split(/\s+/).slice(1);
  if (!versions.some(v => /^1\.8\.4(?:_\d+)?$/.test(v))) {
    throw new Error('Pynini 2.1.7 requires OpenFst 1.8.4; check the installed Homebrew formula');
  }
  for (const file of ['include/fst/util.h', 'include/fst/extensions/far/far.h',
    'lib/libfst.dylib', 'lib/libfstfar.dylib', 'lib/libfstscript.dylib']) {
    if (!exists(path.join(prefix, file))) throw new Error(`OpenFst GRM prerequisite missing: ${file}`);
  }
  const prepend = (name, value, separator) => value + (env[name] ? separator + env[name] : '');
  return { ...env,
    CPLUS_INCLUDE_PATH: prepend('CPLUS_INCLUDE_PATH', path.join(prefix, 'include'), ':'),
    LIBRARY_PATH: prepend('LIBRARY_PATH', path.join(prefix, 'lib'), ':'),
    LDFLAGS: prepend('LDFLAGS', `-L${path.join(prefix, 'lib')}`, ' '),
  };
}

if (require.main === module) {
  const env = prepare();
  if (process.argv.includes('--github-env')) {
    for (const key of ['CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'LDFLAGS']) {
      if (env[key] !== undefined) {
        if (/[\r\n]/.test(env[key])) throw new Error(`Invalid newline in ${key}`);
        fs.appendFileSync(process.env.GITHUB_ENV, `${key}=${env[key]}\n`);
      }
    }
  }
}
module.exports = { prepare };
