import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { generateExtensionTemplate } from '../utils/templates';

export async function initExtension(): Promise<void> {
  console.log(chalk.blue('在当前目录初始化扩展项目...'));
  
  const currentDir = process.cwd();
  const folderName = path.basename(currentDir);
  
  // 检查当前目录是否已经初始化
  if (fs.existsSync(path.join(currentDir, 'ssextension.yaml'))) {
    console.error(chalk.red('错误: 该目录已包含扩展项目'));
    process.exit(1);
  }
  
  // 确认是否继续
  console.log(`将使用文件夹名 "${folderName}" 作为扩展名称`);
  
  try {
    // 使用默认设置生成模板
    await generateExtensionTemplate(currentDir, {
      name: folderName,
      version: '1.0.0',
      description: '',
      usePython: true,
      pythonDependencies: '',
      useWebUI: true
    });
    
    console.log(chalk.green(`\n✅ 扩展 "${folderName}" 初始化成功!`));
    console.log('\n接下来的步骤:');
    console.log(`  ${chalk.yellow('npm install')} # 安装前端依赖`);
    console.log(`  ${chalk.yellow('ssext package')} # 打包扩展`);
  } catch (error) {
    console.error(chalk.red('初始化扩展失败:'), error);
    process.exit(1);
  }
} 