const fs = require('fs');
const path = require('path');
const os = require('os');
const root = path.resolve(__dirname, '..');
function resolveConfig(env = process.env, repo = root, home = os.homedir()) {
  const configPath = env.SSUI_DEV_CONFIG ? path.resolve(repo, env.SSUI_DEV_CONFIG) : path.join(repo, '.ssui-dev.json');
  if (env.SSUI_DEV_CONFIG && !fs.existsSync(configPath)) throw new Error(`Configuration does not exist: ${configPath}`);
  const machinePath = path.join(home, '.ssui-dev', 'config.json');
  const read = file => fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
  const machine = env.SSUI_DEV_CONFIG ? {} : read(machinePath);
  const local = read(configPath);
  const config = { ...machine, ...local };
  const result = { ...env };
  for (const key of ['SSUI_VENV_PATH', 'SSUI_MODEL_DIR', 'TEST_DATA_DIR', 'HF_HOME', 'TORCH_HOME']) {
    const value = env[key] || config[key];
    if (value !== undefined) {
      if (typeof value !== 'string' || !value.trim()) throw new Error(`Invalid path: ${key}`);
      const expanded = value === '~' ? home : /^~[/\\]/.test(value) ? path.join(home, value.slice(2)) : value;
      result[key] = path.resolve(env[key] ? repo : (Object.hasOwn(local, key) ? path.dirname(configPath) : path.dirname(machinePath)), expanded);
    }
  }
  result.SSUI_VENV_PATH ||= path.join(repo, '.venv');
  // Retopology can run in WSL; preserve Linux paths rather than resolving them
  // with the Windows path module. These settings are local machine resources.
  for (const key of ['SSUI_QUADRIFLOW_EXECUTABLE', 'SSUI_QUADRIFLOW_WSL_DISTRO',
    'SSUI_P3SAM_ROOT', 'SSUI_P3SAM_PYTHON', 'SSUI_P3SAM_WSL_DISTRO',
    'SSUI_P3SAM_CHECKPOINT', 'SSUI_SONATA_CHECKPOINT', 'SSUI_P3SAM_BACKEND', 'SSUI_P3SAM_DEVICE', 'SSUI_P3SAM_POINT_NUM',
    'SSUI_P3SAM_PROMPT_NUM', 'SSUI_P3SAM_PROMPT_BATCH', 'SSUI_3D_OUTPUT',
    'SSUI_HOLOPART_ROOT', 'SSUI_HOLOPART_PYTHON', 'SSUI_HOLOPART_WEIGHTS']) {
    const value = env[key] || config[key];
    if (value !== undefined) {
      if (typeof value !== 'string' || !value.trim()) throw new Error(`Invalid setting: ${key}`);
      result[key] = value;
    }
  }
  // Resolve source imports against this checkout even with a shared environment.
  result.PYTHONPATH = [repo, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  result.VIRTUAL_ENV = result.SSUI_VENV_PATH;
  result.PATH = [path.join(result.SSUI_VENV_PATH, process.platform === 'win32' ? 'Scripts' : 'bin'), env.PATH || ''].join(path.delimiter);
  return result;
}
function executable(name, env) {
  return path.join(env.SSUI_VENV_PATH, process.platform === 'win32' ? 'Scripts' : 'bin',
    process.platform === 'win32' && !path.extname(name) ? `${name}.exe` : name);
}
module.exports = { resolveConfig, executable, root };
if (require.main === module) {
  const env = resolveConfig();
  console.log(JSON.stringify(Object.fromEntries(['SSUI_VENV_PATH', 'SSUI_MODEL_DIR', 'TEST_DATA_DIR', 'HF_HOME', 'TORCH_HOME'].map(key => [key, env[key] || null])), null, 2));
}
