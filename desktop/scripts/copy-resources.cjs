const fs = require('fs');
const path = require('path');
const tar = require('tar');
const glob = require('glob');
const ignore = require('ignore');

// 源文件和目标目录路径
const sourceDir = path.resolve(__dirname, '../../dependencies');
const targetDir = path.resolve(__dirname, '../src-tauri/resources/dependencies');
const resourcesDir = path.resolve(__dirname, '../src-tauri/resources');

// 要打包的常规目录
const packDirs = [
  'backend',
  'ssui',
  'ss_executor',
  'server',
];

// 要打包的JS输出目录（忽略gitignore规则）
const packDirsJsOutput = [
  'frontend/functional_ui/dist'
];

const packFiles = [
  'extensions/Readme.md'
];

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

// 读取gitignore文件
function getGitignoreFilter() {
  const gitignorePath = path.resolve(__dirname, '../../.gitignore');
  let ig = ignore();
  
  if (fs.existsSync(gitignorePath)) {
    const gitignoreContent = fs.readFileSync(gitignorePath, 'utf8');
    ig = ignore().add(gitignoreContent);
  }
  
  return ig;
}

// 收集要打包的文件
function collectFilesToPack() {
  const rootDir = path.resolve(__dirname, '../../');
  const ig = getGitignoreFilter();
  const filesToPack = [];
  
  // 处理常规目录（应用gitignore规则）
  for (const dir of packDirs) {
    const fullDirPath = path.join(rootDir, dir);
    if (!fs.existsSync(fullDirPath)) {
      console.warn(`警告: 目录不存在 - ${fullDirPath}`);
      continue;
    }
    
    const files = glob.sync(`${dir}/**/*`, { 
      cwd: rootDir, 
      dot: true,
      nodir: true
    });
    
    for (const file of files) {
      if (!ig.ignores(file)) {
        filesToPack.push(file);
      }
    }
  }
  
  // 处理JS输出目录（忽略gitignore规则）
  for (const dir of packDirsJsOutput) {
    const fullDirPath = path.join(rootDir, dir);
    if (!fs.existsSync(fullDirPath)) {
      console.warn(`警告: 目录不存在 - ${fullDirPath}`);
      continue;
    }
    
    const files = glob.sync(`${dir}/**/*`, { 
      cwd: rootDir, 
      dot: true,
      nodir: true
    });
    
    // 直接添加所有文件，不应用gitignore过滤
    filesToPack.push(...files);
  }

  // 添加packFiles
  filesToPack.push(...packFiles);
  
  return { rootDir, filesToPack };
}

// 创建tar.gz压缩包
async function createTarball() {
  const { rootDir, filesToPack } = collectFilesToPack();
  const outputPath = path.join(resourcesDir, 'app.tar.gz');
  
  console.log(`开始创建压缩包: ${outputPath}`);
  console.log(`将打包 ${filesToPack.length} 个文件`);
  
  ensureDirectoryExists(resourcesDir);
  
  try {
    await tar.create(
      {
        gzip: true,
        file: outputPath,
        cwd: rootDir,
        portable: true,
      },
      filesToPack
    );
    console.log(`压缩包创建成功: ${outputPath}`);
  } catch (err) {
    console.error(`创建压缩包失败: ${err.message}`);
    process.exit(1);
  }
}

// 主函数
async function main() {
  console.log('开始复制lock文件到Tauri资源目录...');
  
  // 确保目标目录存在
  ensureDirectoryExists(targetDir);
  const { wheelhouseFor } = require('../../dependencies/native_wheels.cjs');
  const { getCurrentTarget } = require('../../dependencies/platform.cjs');
  const nativeWheels = wheelhouseFor(getCurrentTarget());
  // Remove stale wheels when switching build targets in the same checkout.
  for (const name of fs.readdirSync(targetDir)) {
    if (name.endsWith('.whl') || name === 'native-wheels.json') fs.unlinkSync(path.join(targetDir, name));
  }
  if (nativeWheels) {
    const manifest = require('../../dependencies/native_wheels.cjs').verifyWheelhouse(nativeWheels);
    for (const wheel of manifest.wheels) copyFile(path.join(nativeWheels, wheel.filename), path.join(targetDir, wheel.filename));
    copyFile(path.join(nativeWheels, 'manifest.json'), path.join(targetDir, 'native-wheels.json'));
  }

  
  // All packaged dependency sets come from the same OS / arch / backend registry.
  const { profiles } = require('../../dependencies/runtime-targets.json');
  for (const { dependencyTarget } of profiles) {
    const source = path.join(sourceDir, `${dependencyTarget}.lock`);
    if (!fs.existsSync(source)) throw new Error(`缺少依赖锁文件: ${source}`);
    copyFile(source, path.join(targetDir, `${dependencyTarget}.lock`));
  }

  // touch 一个文件
  const touchFile = path.join(resourcesDir, 'extensions', 'Readme.md');
  // 确保目录存在
  fs.mkdirSync(path.dirname(touchFile), { recursive: true });
  fs.writeFileSync(touchFile, 'Prebuilt extensions included in the app.');
  
  console.log('资源文件复制完成!');

  // 从 examples/basic 复制官方工作流示例（单一来源，避免两处漂移）
  const workflowSourceDir = path.resolve(__dirname, '../../examples/basic');
  const workflowTargetDir = path.resolve(__dirname, '../src-tauri/workflow/txt2img/basic');
  ensureDirectoryExists(workflowTargetDir);
  if (fs.existsSync(workflowSourceDir)) {
    for (const file of fs.readdirSync(workflowSourceDir)) {
      const src = path.join(workflowSourceDir, file);
      if (fs.statSync(src).isFile()) {
        copyFile(src, path.join(workflowTargetDir, file));
      }
    }
  } else {
    console.warn(`警告: 示例目录不存在 - ${workflowSourceDir}`);
  }

  // 创建app.tar.gz压缩包
  await createTarball();
}

main(); 
