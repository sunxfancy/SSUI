import inquirer from 'inquirer';
import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { generateExtensionTemplate } from '../utils/templates';

interface ExtensionAnswers {
  name: string;
  version: string;
  description: string;
  usePython: boolean;
  pythonDependencies: string;
  useWebUI: boolean;
}

export async function newExtension(): Promise<void> {
  console.log(chalk.blue('创建新扩展项目...'));
  
  const answers = await inquirer.prompt<ExtensionAnswers>([
    {
      type: 'input',
      name: 'name',
      message: '扩展名称:',
      validate: (input) => {
        if (!input.trim()) return '扩展名称不能为空';
        if (fs.existsSync(input)) return `文件夹 "${input}" 已存在`;
        return true;
      }
    },
    {
      type: 'input',
      name: 'version',
      message: '版本号:',
      default: '1.0.0',
      validate: (input) => {
        const valid = /^\d+\.\d+\.\d+$/.test(input);
        return valid || '请输入有效的版本号 (例如: 1.0.0)';
      }
    },
    {
      type: 'input',
      name: 'description',
      message: '扩展描述:',
      default: ''
    },
    {
      type: 'confirm',
      name: 'usePython',
      message: '是否包含 Python 后端?',
      default: true
    },
    {
      type: 'input',
      name: 'pythonDependencies',
      message: '请输入 Python 依赖(以逗号分隔):',
      default: '',
      when: (answers) => answers.usePython,
    },
    {
      type: 'confirm',
      name: 'useWebUI',
      message: '是否包含 Web UI 前端?',
      default: true
    }
  ]);

  // 创建项目目录
  const projectDir = path.resolve(process.cwd(), answers.name);
  await fs.mkdir(projectDir);

  try {
    // 生成项目模板文件
    await generateExtensionTemplate(projectDir, answers);
    
    console.log(chalk.green(`\n✅ 扩展 "${answers.name}" 已成功创建!`));
    console.log(`\n目录: ${chalk.cyan(projectDir)}`);
    console.log('\n接下来的步骤:');
    console.log(`  ${chalk.yellow('cd')} ${answers.name}`);
    if (answers.useWebUI) {
      console.log(`  ${chalk.yellow('npm install')} # 安装前端依赖`);
    }
    console.log(`  ${chalk.yellow('ssext package')} # 打包扩展`);
  } catch (error) {
    console.error(chalk.red('创建扩展失败:'), error);
    // 清理失败的项目目录
    await fs.remove(projectDir);
    process.exit(1);
  }
} 