const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { resolveConfig, executable } = require('./dev_config.cjs');
const devEnv = resolveConfig();
const { getAllTargets, getCurrentPlatformTargets } = require('./platform.cjs');
const { profileFromName, pythonDistribution } = require('./runtime_target.cjs');
const { generateRequirements } = require('./dependency_config.cjs');

// 检查命令行参数
function parseArgs(args = process.argv.slice(2)) {
  const opts = { noUpgrade: false, all: false, targets: [] };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--no-upgrade' || args[i] === '-n') opts.noUpgrade = true;
    else if (args[i] === '--all' || args[i] === '-a') opts.all = true;
    else if (args[i] === '--target') {
      if (!args[i + 1] || args[i + 1].startsWith('-')) throw new Error('--target 缺少目标名称');
      opts.targets.push(profileFromName(args[++i]).dependencyTarget);
    } else throw new Error(`未知参数: ${args[i]}`);
  }
  if (opts.all && opts.targets.length) throw new Error('--all 不能与 --target 同时使用');
  return opts;
}

function compileArgs(target, requirementsFile, lockFile, noUpgrade = false) {
  const profile = profileFromName(target);
  const python = pythonDistribution(profile);
  return ['pip', 'compile', requirementsFile, '-o', lockFile,
    '--python-platform', python.triple, '--python-version', python.version,
    ...(profile.binaryOnly ? ['--no-build', '--index-strategy', 'unsafe-best-match'] : []),
    // uv preserves existing pins by default; there is no --no-upgrade flag.
    ...(noUpgrade ? [] : ['--upgrade'])];
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

// 主函数
function main() {
  try {
    const args = parseArgs();
    // --all 生成全部目标，否则只生成当前平台下的所有变体（含 GPU 变体）
    const targets = args.targets.length ? [...new Set(args.targets)] : args.all ? getAllTargets() : getCurrentPlatformTargets();
    if (targets.length === 0) throw new Error('当前 OS / 架构尚未提供依赖配置，无法生成锁文件');
    
    for (const targetName of targets) {
      const requirementsFile = path.relative(process.cwd(), generateRequirements(targetName));
      const lockFile = path.join('.', 'dependencies', `${targetName}.lock`);
      
      // 提取requirements文件中的index-url信息
      const indexUrls = extractIndexUrls(requirementsFile);
      if (indexUrls.length > 0) {
        console.log(`发现以下index URL配置 (${targetName}):`, indexUrls);
      }

      console.log(`正在为目标 ${targetName} 生成锁文件...`);
      
      // 构建uv命令，根据参数决定是否添加--no-upgrade选项
      const venvPath = process.env.SSUI_UV_PATH || executable('uv', devEnv);
      if (args.noUpgrade) {
        console.log('使用不升级模式: 已存在的包将不会升级到最新版本');
      }
      
      // 使用uv生成锁文件
      execFileSync(venvPath, compileArgs(targetName, requirementsFile, lockFile, args.noUpgrade), { stdio: 'inherit', env: devEnv });
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
      const yamlFile = path.join('.', 'dependencies', `${targetName}-dependencies.yaml`);
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
  // Keep uv's # via comments: they carry root and reverse-dependency edges.
  const cleanContent = content.split('\n').filter(line => !line.startsWith('--')).join('\n');

  const dependencies = {};
  // 将锁文件按包分块，每个包以非空格开头的行为起始
  const packageBlocks = cleanContent.split(/\n(?=[a-zA-Z0-9._-]+(?:==| @ ))/);
  
  for (const block of packageBlocks) {
    if (!block.trim()) continue;
    
    const lines = block.split('\n');
    const firstLine = lines[0];
    
    // 检查是否为包定义行，并提取版本信息
    const packageMatch = firstLine.match(/^([a-zA-Z0-9._-]+)(?:==(.+)| @ (https?:\/\/\S+))$/);
    if (!packageMatch) continue;
    
    const packageName = packageMatch[1].toLowerCase();
    const url = packageMatch[3];
    const filename = url && decodeURIComponent(new URL(url).pathname.split('/').pop());
    const version = packageMatch[2] || (filename?.endsWith('.whl') ? filename.split('-')[1] : url);
    dependencies[packageName] = { 
      version: version,
      dependents: [], 
      isRoot: false 
    };
    if (url) dependencies[packageName].url = url;
    
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
    if (info.url) yaml += `  url: ${JSON.stringify(info.url)}\n`;
    
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
if (require.main === module) main();
module.exports = { parseArgs, compileArgs, parseLockFile, generateYaml };
