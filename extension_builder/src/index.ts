#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { newExtension } from './commands/new';
import { initExtension } from './commands/init';
import { packageExtension } from './commands/package';

const program = new Command();

program
  .name('ssext')
  .description('扩展构建工具')
  .version('0.1.0');

program
  .command('new')
  .description('交互式创建一个新的扩展')
  .action(newExtension);

program
  .command('init')
  .description('使用当前文件夹名称初始化扩展项目')
  .action(initExtension);

program
  .command('package')
  .description('将扩展打包成 tar.gz 文件')
  .option('-o, --output <string>', '指定输出路径')
  .action((options) => packageExtension(options.output));

// 处理未知命令
program.on('command:*', (operands) => {
  console.error(chalk.red(`错误: 未知命令 '${operands[0]}'`));
  const availableCommands = program.commands.map(cmd => cmd.name());
  console.error(chalk.yellow(`可用命令: ${availableCommands.join(', ')}`));
  process.exitCode = 1;
});

program.parse(process.argv);

// 如果没有提供参数，显示帮助信息
if (!process.argv.slice(2).length) {
  program.outputHelp();
} 