const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { getCurrentTarget } = require('./platform.cjs');

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
    console.log(`Installing requirements from: ${requirementsFile}`);
    
    // 使用 venv.cjs 来执行 uv pip 命令
    execSync(`node ${path.join(__dirname, 'venv.cjs')} uv pip install -r "${requirementsFile}"`, {
        stdio: 'inherit'
    });
    
    console.log('Requirements installed successfully!');
} catch (error) {
    console.error('Error installing requirements:', error.message);
    process.exit(1);
} 