const { platform } = require('os');
const { execSync } = require('child_process');
const path = require('path');

function getRequirementsFile() {
    const os = platform();
    if (os === 'win32') {
        return path.join(__dirname, 'requirements-windows.txt');
    } else if (os === 'darwin') {
        return path.join(__dirname, 'requirements-macosx.txt');
    } else {
        throw new Error(`Unsupported operating system: ${os}`);
    }
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