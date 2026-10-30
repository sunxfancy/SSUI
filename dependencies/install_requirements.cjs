const { resolveConfig, root, executable } = require('./dev_config.cjs');
const devEnv = resolveConfig();
const { execSync, execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { getCurrentTarget, getRuntimeTarget } = require('./platform.cjs');
const { assertPythonRuntime, dependencyProfile } = require('./runtime_target.cjs');

function getRequirementsFile() {
    // 目标名（如 windows / windows-amdgpu / linux-amdgpu / macosx）直接对应锁文件
    const target = getCurrentTarget();
    const lockFile = path.join(__dirname, `${target}.lock`);
    if (!fs.existsSync(lockFile)) {
        throw new Error(`找不到锁文件: ${lockFile}，请先运行 \`yarn update-lock\` 生成`);
    }
    return lockFile;
}

try {
    const requirementsFile = getRequirementsFile();
    const pythonRuntime = JSON.parse(execFileSync(executable('python', devEnv), [
        '-c', 'import json, platform, sys; print(json.dumps({"os": sys.platform, "arch": platform.machine()}))'
    ], { encoding: 'utf8', env: devEnv }));
    assertPythonRuntime(getRuntimeTarget(), pythonRuntime);
    const binaryOnly = dependencyProfile(getRuntimeTarget()).binaryOnly ? ' --only-binary :all:' : '';
    const nativeWheels = require('./native_wheels.cjs').wheelhouseFor(getCurrentTarget());
    console.log(`Installing requirements from: ${requirementsFile}`);
    
    // 使用 venv.cjs 来执行 uv pip 命令
    // --index-strategy unsafe-best-match: 锁文件中 torch 的 extra-index-url 排在前，
    // 但部分包（如 importlib-metadata）只在 PyPI 上，uv 默认只查第一个 index。
    execFileSync(process.execPath, [path.join(__dirname, 'venv.cjs'), 'uv', 'pip', 'install',
        '-r', requirementsFile, '--index-strategy', 'unsafe-best-match',
        '--build-constraint', path.join(__dirname, 'build-constraints.txt'),
        ...(binaryOnly ? ['--only-binary', ':all:'] : []),
        ...(nativeWheels ? ['--find-links', nativeWheels] : [])], {
        stdio: 'inherit', env: devEnv, cwd: root
    });
    
    // Shared venvs must not pin imports to one worktree through editable installs.
    if (path.resolve(devEnv.SSUI_VENV_PATH) === path.join(root, '.venv')) {
        execSync(`node "${path.join(__dirname, 'venv.cjs')}" python -m pip install -e .`, {
            stdio: 'inherit', env: devEnv, cwd: root
        });
    }
    console.log('Requirements installed successfully!');
} catch (error) {
    console.error('Error installing requirements:', error.message);
    process.exit(1);
} 
