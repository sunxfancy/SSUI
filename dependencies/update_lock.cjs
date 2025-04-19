const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// 检查命令行参数
function parseArgs() {
  const args = process.argv.slice(2);
  return {
    noUpgrade: args.includes('--no-upgrade') || args.includes('-n')
  };
}

// 确定当前操作系统
function getPlatformName() {
  const platform = os.platform();
  if (platform === 'win32') return 'windows';
  if (platform === 'darwin') return 'macosx';
  return 'linux'; // 默认为linux
}

// 读取requirements文件并提取index-url信息
function extractIndexUrls(requirementsFile) {
  const content = fs.readFileSync(requirementsFile, 'utf8');
  const lines = content.split('\n');
  
  const indexUrls = [];
  for (const line of lines) {
    // 检查是否包含index url信息
    if (line.trim().startsWith('--extra-index-url') || 
        line.trim().startsWith('--index-url') || 
        line.trim().startsWith('-i ')) {
      indexUrls.push(line.trim());
    }
  }
  
  return indexUrls;
}

// 获取所有支持的平台列表
function getAllPlatforms() {
  return ['windows', 'macosx', 'linux'];
}

// 主函数
function main() {
  try {
    const args = parseArgs();
    const platforms = getAllPlatforms();
    
    for (const platformName of platforms) {
      const requirementsFile = path.join('.', 'dependencies', `requirements-${platformName}.txt`);
      const lockFile = path.join('.', 'dependencies', `${platformName}.lock`);
      
      // 检查requirements文件是否存在
      if (!fs.existsSync(requirementsFile)) {
        console.log(`跳过平台 ${platformName}: 未找到requirements文件: ${requirementsFile}`);
        continue;
      }

      // 提取requirements文件中的index-url信息
      const indexUrls = extractIndexUrls(requirementsFile);
      if (indexUrls.length > 0) {
        console.log(`发现以下index URL配置 (${platformName}):`, indexUrls);
      }

      console.log(`正在为平台 ${platformName} 生成锁文件...`);
      
      // 构建uv命令，根据参数决定是否添加--no-upgrade选项
      const venvPath = os.platform() === 'win32' ? '.venv\\Scripts\\uv.exe' : '.venv/bin/uv';
      let uvCommand = `${venvPath} pip compile ${requirementsFile} -o ${lockFile}`;
      if (args.noUpgrade) {
        console.log('使用不升级模式: 已存在的包将不会升级到最新版本');
        uvCommand += ' --no-upgrade';
      }
      
      // 使用uv生成锁文件
      execSync(uvCommand, { stdio: 'inherit' });
      console.log(`已生成锁文件: ${lockFile}`);
      
      // 如果有index URL，将其添加到锁文件末尾
      if (indexUrls.length > 0) {
        console.log('正在将index URL信息添加到锁文件...');
        let lockContent = fs.readFileSync(lockFile, 'utf8');
        
        // 添加index URLs
        for (const url of indexUrls) {
          lockContent += `${url}\n`;
        }
        
        fs.writeFileSync(lockFile, lockContent);
        console.log('已将index URL信息添加到锁文件');
      }
      
      // 读取并解析锁文件
      const lockContent = fs.readFileSync(lockFile, 'utf8');
      const dependencies = parseLockFile(lockContent);
      
      // 生成YAML文件
      const yamlContent = generateYaml(dependencies);
      const yamlFile = path.join('.', 'dependencies', `${platformName}-dependencies.yaml`);
      fs.writeFileSync(yamlFile, yamlContent);
      
      console.log(`已生成依赖YAML文件: ${yamlFile}`);
      console.log('-----------------------------------');
    }
  } catch (error) {
    console.error('执行过程中出错:', error);
    process.exit(1);
  }
}

// 解析锁文件内容
function parseLockFile(content) {
  // 首先去除文件末尾的index URL注释部分
  cleanContent = content.split('\n').filter(line => !line.startsWith('#') && !line.startsWith('--extra-index-url')).join('\n');

  const dependencies = {};
  // 将锁文件按包分块，每个包以非空格开头的行为起始
  const packageBlocks = cleanContent.split(/\n(?=[a-zA-Z0-9._-]+==)/);
  
  for (const block of packageBlocks) {
    if (!block.trim()) continue;
    
    const lines = block.split('\n');
    const firstLine = lines[0];
    
    // 检查是否为包定义行，并提取版本信息
    const packageMatch = firstLine.match(/^([a-zA-Z0-9._-]+)==(.+)$/);
    if (!packageMatch) continue;
    
    const packageName = packageMatch[1].toLowerCase();
    const version = packageMatch[2];
    dependencies[packageName] = { 
      version: version,
      dependents: [], 
      isRoot: false 
    };
    
    // 合并所有 via 行
    let viaContent = '';
    let foundVia = false;
    
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('# via')) {
        foundVia = true;
        viaContent += line.substring(5).trim() + ' ';
      } else if (line.startsWith('#') && foundVia) {
        // 这是一个续行的注释
        viaContent += line.substring(1).trim() + ' ';
      }
    }
    
    // 检查是否包含 -r dependencies/xxx.txt 引用
    if (viaContent.includes('-r dependencies/') || viaContent.includes('-r ./dependencies/')) {
      // 这是一个根依赖，直接从requirements文件中引入
      dependencies[packageName].isRoot = true;
    }
    
    // 处理依赖信息
    if (viaContent) {
      // 清理并分割依赖项
      const deps = viaContent
        .replace(/-r\s+[^\s]+/g, '') // 移除 -r dependencies/xxx.txt 引用但保留记录
        .split(/\s+/)
        .filter(dep => dep && dep !== '' && !dep.includes('/'));
      
      // 添加到依赖列表
      for (const dep of deps) {
        if (dep && !dependencies[packageName].dependents.includes(dep)) {
          dependencies[packageName].dependents.push(dep);
        }
      }
    }
  }
  
  return dependencies;
}

// 生成YAML文件
function generateYaml(dependencies) {
  let yaml = '# 包依赖关系\n';
  
  for (const [packageName, info] of Object.entries(dependencies)) {
    yaml += `${packageName}:\n`;
    
    // 添加版本信息
    yaml += `  version: "${info.version}"\n`;
    
    // 添加根依赖标志
    if (info.isRoot) {
      yaml += `  isRoot: ${info.isRoot}\n`;
    }
    
    if (info.dependents && info.dependents.length > 0) {
      yaml += '  dependents:\n';
      // 去重依赖列表
      const uniqueDependents = [...new Set(info.dependents)];
      for (const dependent of uniqueDependents) {
        yaml += `    - ${dependent}\n`;
      }
    } 
  }
  
  return yaml;
}

// 执行主函数
main();
