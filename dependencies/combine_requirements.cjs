const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const os = require('os');
const semver = require('semver');

// 确保.build目录存在
const buildDir = path.join(__dirname, '..', '.build');
if (!fs.existsSync(buildDir)) {
  fs.mkdirSync(buildDir, { recursive: true });
}

// 确定当前平台
function getPlatform() {
  const platform = os.platform();
  if (platform === 'win32') return 'windows';
  if (platform === 'darwin') return 'mac';
  if (platform === 'linux') return 'linux';
  return 'common'; // 默认平台
}

// 解析版本约束
function parseVersionConstraint(constraint) {
  if (!constraint) return null;
  
  constraint = constraint.trim();
  
  // 处理常见的版本格式
  if (constraint.startsWith('^')) {
    const version = constraint.substring(1);
    return {
      min: version,
      max: `${semver.major(version) + 1}.0.0`,
      includeMin: true,
      includeMax: false
    };
  } else if (constraint.startsWith('~')) {
    const version = constraint.substring(1);
    return {
      min: version,
      max: `${semver.major(version)}.${semver.minor(version) + 1}.0`,
      includeMin: true,
      includeMax: false
    };
  } else if (constraint.startsWith('>=')) {
    return {
      min: constraint.substring(2).trim(),
      max: null,
      includeMin: true,
      includeMax: false
    };
  } else if (constraint.startsWith('>')) {
    return {
      min: constraint.substring(1).trim(),
      max: null,
      includeMin: false,
      includeMax: false
    };
  } else if (constraint.startsWith('<=')) {
    return {
      min: null,
      max: constraint.substring(2).trim(),
      includeMin: false,
      includeMax: true
    };
  } else if (constraint.startsWith('<')) {
    return {
      min: null,
      max: constraint.substring(1).trim(),
      includeMin: false,
      includeMax: false
    };
  } else if (constraint.startsWith('=') || /^[0-9]/.test(constraint)) {
    const version = constraint.startsWith('=') ? constraint.substring(1).trim() : constraint;
    return {
      min: version,
      max: version,
      includeMin: true,
      includeMax: true
    };
  }
  
  return null;
}

// 计算两个版本约束的交集
function mergeConstraints(constraint1, constraint2) {
  if (!constraint1) return constraint2;
  if (!constraint2) return constraint1;
  
  const result = {
    min: null,
    max: null,
    includeMin: false,
    includeMax: false
  };
  
  // 计算最小版本
  if (constraint1.min === null) {
    result.min = constraint2.min;
    result.includeMin = constraint2.includeMin;
  } else if (constraint2.min === null) {
    result.min = constraint1.min;
    result.includeMin = constraint1.includeMin;
  } else {
    const comparison = semver.compare(constraint1.min, constraint2.min);
    if (comparison > 0) {
      result.min = constraint1.min;
      result.includeMin = constraint1.includeMin;
    } else if (comparison < 0) {
      result.min = constraint2.min;
      result.includeMin = constraint2.includeMin;
    } else { // 版本相等
      result.min = constraint1.min;
      result.includeMin = constraint1.includeMin && constraint2.includeMin;
    }
  }
  
  // 计算最大版本
  if (constraint1.max === null) {
    result.max = constraint2.max;
    result.includeMax = constraint2.includeMax;
  } else if (constraint2.max === null) {
    result.max = constraint1.max;
    result.includeMax = constraint1.includeMax;
  } else {
    const comparison = semver.compare(constraint1.max, constraint2.max);
    if (comparison < 0) {
      result.max = constraint1.max;
      result.includeMax = constraint1.includeMax;
    } else if (comparison > 0) {
      result.max = constraint2.max;
      result.includeMax = constraint2.includeMax;
    } else { // 版本相等
      result.max = constraint1.max;
      result.includeMax = constraint1.includeMax && constraint2.includeMax;
    }
  }
  
  // 检查约束是否有效
  if (result.min && result.max && semver.compare(result.min, result.max) > 0) {
    throw new Error(`版本约束不兼容: ${formatConstraint(constraint1)} 与 ${formatConstraint(constraint2)}`);
  }
  
  return result;
}

// 格式化约束为字符串
function formatConstraint(constraint) {
  if (!constraint) return '';
  if (!constraint.min && !constraint.max) return '';
  
  if (constraint.min && constraint.max) {
    if (constraint.min === constraint.max && constraint.includeMin && constraint.includeMax) {
      return `==${constraint.min}`;
    } else {
      const minOp = constraint.includeMin ? '>=' : '>';
      const maxOp = constraint.includeMax ? '<=' : '<';
      return `${minOp}${constraint.min},${maxOp}${constraint.max}`;
    }
  } else if (constraint.min) {
    const op = constraint.includeMin ? '>=' : '>';
    return `${op}${constraint.min}`;
  } else if (constraint.max) {
    const op = constraint.includeMax ? '<=' : '<';
    return `${op}${constraint.max}`;
  }
  
  return '';
}

// 读取根目录下依赖
function loadCoreDependencies() {
  const platform = getPlatform();
  const dependenciesPath = path.join(__dirname, '..', 'dependencies', `requirements-${platform}.txt`);
  
  if (!fs.existsSync(dependenciesPath)) {
    console.warn(`找不到平台特定的依赖文件: ${dependenciesPath}, 尝试使用通用依赖`);
    const commonPath = path.join(__dirname, '..', 'dependencies', 'requirements-common.txt');
    if (!fs.existsSync(commonPath)) {
      console.warn('找不到通用依赖文件');
      return {};
    }
    return parseDependenciesFile(commonPath);
  }
  
  return parseDependenciesFile(dependenciesPath);
}

// 解析依赖文件
function parseDependenciesFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const dependencies = {};
  
  content.split('\n').forEach(line => {
    line = line.trim();
    if (line && !line.startsWith('#')) {
      const [name, version] = parseRequirement(line);
      dependencies[name] = parseVersionConstraint(version);
    }
  });
  
  return dependencies;
}

// 解析单个依赖
function parseRequirement(req) {
  const parts = req.split('=');
  if (parts.length === 1) {
    return [parts[0].trim(), null];
  } else if (parts.length >= 2) {
    const name = parts[0].trim();
    const version = parts.slice(1).join('=').trim();
    return [name, version];
  }
}

// 扫描扩展依赖
function scanExtensionDependencies() {
  const extensionsDir = path.join(__dirname, '..', 'extensions');
  const dependencies = {};
  
  if (!fs.existsSync(extensionsDir)) {
    console.warn('找不到扩展目录');
    return dependencies;
  }
  
  const extensions = fs.readdirSync(extensionsDir, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name);
  
  extensions.forEach(extension => {
    const configPath = path.join(extensionsDir, extension, 'ssextension.yaml');
    if (fs.existsSync(configPath)) {
      try {
        const config = yaml.load(fs.readFileSync(configPath, 'utf8'));
        if (config.server && Array.isArray(config.server.dependencies)) {
          config.server.dependencies.forEach(dep => {
            const [name, version] = parseRequirement(dep);
            if (!dependencies[name]) {
              dependencies[name] = parseVersionConstraint(version);
            } else {
              try {
                dependencies[name] = mergeConstraints(dependencies[name], parseVersionConstraint(version));
              } catch (error) {
                console.error(`扩展 ${extension} 的依赖 ${name} 版本冲突: ${error.message}`);
              }
            }
          });
        }
      } catch (error) {
        console.error(`解析扩展 ${extension} 的配置文件时出错: ${error.message}`);
      }
    }
  });
  
  return dependencies;
}

// 合并所有依赖
function combineDependencies() {
  const coreDeps = loadCoreDependencies();
  const extensionDeps = scanExtensionDependencies();
  const allDeps = { ...coreDeps };
  
  // 合并扩展依赖
  Object.entries(extensionDeps).forEach(([name, constraint]) => {
    if (!allDeps[name]) {
      allDeps[name] = constraint;
    } else {
      try {
        allDeps[name] = mergeConstraints(allDeps[name], constraint);
      } catch (error) {
        console.error(`依赖 ${name} 版本冲突: ${error.message}`);
      }
    }
  });
  
  return allDeps;
}

// 将合并后的依赖写入文件
function writeRequirements(dependencies) {
  const outputPath = path.join(buildDir, 'requirements.txt');
  const lines = Object.entries(dependencies)
    .map(([name, constraint]) => `${name}${constraint ? formatConstraint(constraint) : ''}`)
    .sort();
  
  fs.writeFileSync(outputPath, lines.join('\n'));
  console.log(`已生成合并的依赖文件: ${outputPath}`);
}

// 主函数
function main() {
  try {
    const dependencies = combineDependencies();
    writeRequirements(dependencies);
  } catch (error) {
    console.error('合并依赖时出错:', error);
    process.exit(1);
  }
}

main();
