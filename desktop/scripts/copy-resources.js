const fs = require('fs');
const path = require('path');

// 源文件和目标目录路径
const sourceDir = path.resolve(__dirname, '../src/assets');
const targetDir = path.resolve(__dirname, '../src-tauri/resources/dependencies');

// 确保目标目录存在
function ensureDirectoryExists(directory) {
  if (!fs.existsSync(directory)) {
    console.log(`创建目录: ${directory}`);
    fs.mkdirSync(directory, { recursive: true });
  }
}

// 复制文件
function copyFile(source, target) {
  try {
    const data = fs.readFileSync(source);
    fs.writeFileSync(target, data);
    console.log(`成功复制: ${source} -> ${target}`);
  } catch (err) {
    console.error(`复制文件失败: ${err.message}`);
    process.exit(1);
  }
}

// 主函数
function main() {
  console.log('开始复制lock文件到Tauri资源目录...');
  
  // 确保目标目录存在
  ensureDirectoryExists(targetDir);
  
  // 复制Windows lock文件
  const windowsLockSource = path.join(sourceDir, 'windows.lock');
  const windowsLockTarget = path.join(targetDir, 'windows.lock');
  if (fs.existsSync(windowsLockSource)) {
    copyFile(windowsLockSource, windowsLockTarget);
  } else {
    console.warn(`警告: 源文件不存在 - ${windowsLockSource}`);
  }
  
  // 复制MacOS lock文件
  const macosLockSource = path.join(sourceDir, 'macosx.lock');
  const macosLockTarget = path.join(targetDir, 'macosx.lock');
  if (fs.existsSync(macosLockSource)) {
    copyFile(macosLockSource, macosLockTarget);
  } else {
    console.warn(`警告: 源文件不存在 - ${macosLockSource}`);
  }
  
  console.log('资源文件复制完成!');
}

main(); 