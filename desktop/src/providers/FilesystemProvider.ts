import { TreeNodeInfo } from "@blueprintjs/core";
import { readDir, writeTextFile, remove } from '@tauri-apps/plugin-fs';
import { join } from '@tauri-apps/api/path';

export interface IFilesystemProvider {
    fetchFileTree(directory: string, parent: ExtendTreeNodeInfo | null): Promise<ExtendTreeNodeInfo[]>;
    getPathToRoot(node: TreeNodeInfo): string[];
    /** 在指定目录下新建空文件，成功返回完整路径，失败返回 null */
    createFile(parentPath: string, name: string): Promise<string | null>;
    /** 在指定目录下新建绘图板文件（自动补 .canvas 后缀），成功返回完整路径，失败返回 null */
    createCanvas(parentPath: string, name: string): Promise<string | null>;
    /** 删除文件或目录（目录递归删除），成功返回 true */
    deletePath(path: string): Promise<boolean>;
}

export interface ExtendTreeNodeInfo extends TreeNodeInfo {
    isFile: boolean
    nodeData: TreeNodeInfo['nodeData'] & { path: string },
    childNodes?: Array<ExtendTreeNodeInfo>
}

export class TauriFilesystemProvider implements IFilesystemProvider {
    private ignoredPaths: string[] = [
        '.git',
        '__pycache__',
        '.idea',
        '.vscode',
        '.DS_Store',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.pytest_cache',
        '.env',
        'venv',
        '.venv'
    ];

    async fetchFileTree(directory: string, parent: TreeNodeInfo | null = null): Promise<ExtendTreeNodeInfo[]> {
        try {
            console.log('fetchFileTree', directory);
            const files = await readDir(directory);

            // 过滤掉被忽略的文件和目录
            const filteredFiles = files.filter(file => {
                return !this.ignoredPaths.some(ignorePath => {
                    if (ignorePath.startsWith('*')) {
                        const extension = ignorePath.slice(1);
                        return file.name.endsWith(extension);
                    }
                    return file.name === ignorePath;
                });
            });

            return await Promise.all(filteredFiles.map(async (file) => ({
                id: file.name,
                label: file.name,
                isFile: !file.isDirectory,
                nodeData: {
                    path: await join(directory, file.name),
                    parent: parent
                },
                childNodes: file.isDirectory ? [] : undefined
            })));
        } catch (error) {
            console.error("Error reading directory:", error);
            return [];
        }
    }

    getPathToRoot(node: TreeNodeInfo): string[] {
        const path = [];
        let currentNode: TreeNodeInfo | null = node;
        while (currentNode) {
            path.unshift(currentNode.id as string);
            currentNode = (currentNode.nodeData as any)?.parent as TreeNodeInfo | null;
        }
        return path;
    }

    async createFile(parentPath: string, name: string): Promise<string | null> {
        try {
            if (!name.trim()) {
                throw new Error('File name is empty');
            }
            const fullPath = await join(parentPath, name);
            await writeTextFile(fullPath, '');
            return fullPath;
        } catch (error) {
            console.error('Error creating file:', error);
            return null;
        }
    }

    async createCanvas(parentPath: string, name: string): Promise<string | null> {
        const canvasName = name.trim().endsWith('.canvas') ? name.trim() : `${name.trim()}.canvas`;
        return this.createFile(parentPath, canvasName);
    }

    async deletePath(path: string): Promise<boolean> {
        try {
            await remove(path, { recursive: true });
            return true;
        } catch (error) {
            console.error('Error deleting path:', error);
            return false;
        }
    }
}

export default TauriFilesystemProvider;
