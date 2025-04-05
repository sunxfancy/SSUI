import fs from 'fs-extra';
import path from 'path';

/**
 * 递归复制文件和目录，但排除特定目录
 */
export async function copyFilesExcept(
  source: string, 
  target: string, 
  exclude: string[] = []
): Promise<void> {
  const excludeSet = new Set(exclude.map(e => path.resolve(source, e)));
  
  // 检查源路径是否存在
  if (!await fs.pathExists(source)) {
    throw new Error(`源路径不存在: ${source}`);
  }
  
  // 确保目标目录存在
  await fs.ensureDir(target);
  
  // 获取源目录内容
  const items = await fs.readdir(source);
  
  for (const item of items) {
    const sourcePath = path.join(source, item);
    const targetPath = path.join(target, item);
    
    // 检查是否在排除列表中
    if (excludeSet.has(path.resolve(sourcePath))) {
      continue;
    }
    
    const stats = await fs.stat(sourcePath);
    
    if (stats.isDirectory()) {
      // 递归复制目录
      await copyFilesExcept(sourcePath, targetPath, exclude);
    } else {
      // 复制文件
      await fs.copy(sourcePath, targetPath);
    }
  }
} 