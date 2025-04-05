import fs from 'fs-extra';
import path from 'path';
import { execSync } from 'child_process';
import chalk from 'chalk';
import tar from 'tar';
import YAML from 'yaml';

export async function packageExtension(outputDir?: string): Promise<void> {
  console.log(chalk.blue('打包扩展...'));
  
  const currentDir = process.cwd();
  
  // 如果指定了输出目录，确保它存在
  if (outputDir) {
    await fs.ensureDir(outputDir);
    console.log(chalk.blue(`将输出到指定目录: ${outputDir}`));
  }
  
  // 检查是否有扩展配置文件
  const configPath = path.join(currentDir, 'ssextension.yaml');
  if (!fs.existsSync(configPath)) {
    console.error(chalk.red('错误: 未找到 ssextension.yaml 文件'));
    console.error(chalk.yellow('请确保您在扩展目录中运行此命令'));
    process.exit(1);
  }
  
  try {
    // 解析配置文件
    const configFile = fs.readFileSync(configPath, 'utf8');
    const config = YAML.parse(configFile);
    
    // 检查package.json并执行打包命令
    const packageJsonPath = path.join(currentDir, 'package.json');
    if (fs.existsSync(packageJsonPath)) {
      console.log(chalk.yellow('检测到 package.json, 执行打包命令...'));
      
      const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
      if (packageJson.scripts && packageJson.scripts.package) {
        console.log(`执行: npm run package`);
        execSync('npm run package', { stdio: 'inherit' });
      } else {
        console.log(chalk.yellow('未找到 package 脚本, 执行默认构建...'));
        if (packageJson.scripts && packageJson.scripts.build) {
          console.log(`执行: npm run build`);
          execSync('npm run build', { stdio: 'inherit' });
        }
      }
    }
    
    // 创建临时目录存放打包文件
    const tempDir = path.join(currentDir, '.tmp_package');
    await fs.ensureDir(tempDir);
    
    try {
      // 复制必要文件到临时目录
      await fs.copy(configPath, path.join(tempDir, 'ssextension.yaml'));
      
      // 复制Python文件
      if (config.server && config.server.main) {
        const mainPyFile = path.join(currentDir, config.server.main);
        if (fs.existsSync(mainPyFile)) {
          await fs.copy(mainPyFile, path.join(tempDir, config.server.main));
        } else {
          console.warn(chalk.yellow(`警告: 未找到主Python文件 ${config.server.main}`));
        }
      }
      
      // 复制Web UI文件
      if (config.web_ui && config.web_ui.dist) {
        const distDir = path.join(currentDir, config.web_ui.dist);
        if (fs.existsSync(distDir)) {
          await fs.copy(distDir, path.join(tempDir, 'dist'));
        } else {
          console.warn(chalk.yellow(`警告: 未找到Web UI构建目录 ${config.web_ui.dist}`));
        }
      }
      
      // 创建tar.gz包
      const tarName = `${config.name}-${config.version}.tar.gz`;
      const tarOutputPath = outputDir 
        ? path.join(outputDir, tarName) 
        : path.join(currentDir, tarName);
        
      console.log(chalk.green(`创建压缩包: ${tarName}`));
      
      await tar.create(
        {
          gzip: true,
          file: tarOutputPath,
          cwd: tempDir
        },
        await fs.readdir(tempDir)
      );
      
      console.log(chalk.green(`\n✅ 扩展已成功打包! 文件: ${tarOutputPath}`));
    } finally {
      // 清理临时目录
      await fs.remove(tempDir);
    }
    
  } catch (error) {
    console.error(chalk.red('打包扩展失败:'), error);
    process.exit(1);
  }
} 