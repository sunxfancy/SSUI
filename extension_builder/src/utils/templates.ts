import fs from 'fs-extra';
import path from 'path';
import YAML from 'yaml';

interface ExtensionConfig {
  name: string;
  version: string;
  description?: string;
  usePython: boolean;
  pythonDependencies: string;
  useWebUI: boolean;
}

export async function generateExtensionTemplate(
  projectDir: string, 
  config: ExtensionConfig
): Promise<void> {
  // 创建基本目录结构
  if (config.useWebUI) {
    await fs.ensureDir(path.join(projectDir, 'src'));
    await fs.ensureDir(path.join(projectDir, 'dist'));
  }
  
  // 生成 ssextension.yaml
  const yamlConfig: any = {
    name: config.name,
    version: config.version
  };
  
  if (config.description) {
    yamlConfig.description = config.description;
  }
  
  if (config.usePython) {
    yamlConfig.server = {
      venv: 'shared',
      main: `${config.name.toLowerCase()}_extension.py`
    };
    
    if (config.pythonDependencies) {
      yamlConfig.server.dependencies = config.pythonDependencies
        .split(',')
        .map(dep => dep.trim())
        .filter(dep => dep);
    }
    
    // 创建 Python 模板文件
    const pyFileName = `${config.name.toLowerCase()}_extension.py`;
    const pyContent = `
# ${config.name} Extension

def register_extension():
    """注册扩展"""
    return {
        "name": "${config.name}",
        "version": "${config.version}"
    }
`;
    await fs.writeFile(path.join(projectDir, pyFileName), pyContent.trim());
  }
  
  if (config.useWebUI) {
    yamlConfig.web_ui = {
      dist: 'dist/',
      main: 'main.js'
    };
    
    // 创建 package.json
    const packageJson = {
      name: config.name.toLowerCase(),
      version: config.version,
      private: true,
      scripts: {
        build: "tsc",
        package: "tsc"
      },
      devDependencies: {
        typescript: "^5.0.0"
      }
    };
    await fs.writeFile(
      path.join(projectDir, 'package.json'),
      JSON.stringify(packageJson, null, 2)
    );
    
    // 创建 tsconfig.json
    const tsConfig = {
      compilerOptions: {
        target: "ES2020",
        useDefineForClassFields: true,
        module: "ESNext",
        lib: ["ES2020", "DOM", "DOM.Iterable"],
        skipLibCheck: true,
        moduleResolution: "bundler",
        allowImportingTsExtensions: true,
        resolveJsonModule: true,
        isolatedModules: true,
        noEmit: false,
        outDir: "./dist",
        strict: true,
      },
      include: ["src"]
    };
    await fs.writeFile(
      path.join(projectDir, 'tsconfig.json'),
      JSON.stringify(tsConfig, null, 2)
    );
    
    // 创建简单的入口文件
    const mainTs = `
// ${config.name} Extension

export function init() {
  console.log("${config.name} Extension Initialized");
  return {
    name: "${config.name}",
    version: "${config.version}"
  };
}
`;
    await fs.writeFile(path.join(projectDir, 'src', 'main.ts'), mainTs.trim());
  }
  
  // 写入配置文件
  await fs.writeFile(
    path.join(projectDir, 'ssextension.yaml'),
    YAML.stringify(yamlConfig)
  );
  
  // 创建 README.md
  const readme = `# ${config.name} 扩展

${config.description || ''}

## 开发

${config.useWebUI ? '运行 `npm install` 安装依赖。\n\n运行 `npm run build` 构建前端。\n\n' : ''}运行 \`ssext package\` 打包扩展。
`;
  await fs.writeFile(path.join(projectDir, 'README.md'), readme);
} 