const { spawnSync } = require('node:child_process');

const args = ['build', '--target', 'web', '--out-dir', 'pkg'];
// wasm-pack has no wasm-opt download for native Windows ARM64. Cargo's
// release optimization still applies; only the optional Binaryen pass is skipped.
if (process.platform === 'win32' && process.arch === 'arm64') {
  args.push('--no-opt');
}
args.push(...process.argv.slice(2));
const result = spawnSync('wasm-pack', args, { stdio: 'inherit', windowsHide: true });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
