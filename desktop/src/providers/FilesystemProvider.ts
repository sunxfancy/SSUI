import { TreeNodeInfo } from "@blueprintjs/core";
import { readDir } from '@tauri-apps/plugin-fs';
import { join } from '@tauri-apps/api/path';

export interface IFilesystemProvider {
    fetchFileTree(directory: string, parent: TreeNodeInfo | null): Promise<TreeNodeInfo[]>;
    getPathToRoot(node: TreeNodeInfo): string[];
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

    async fetchFileTree(directory: string, parent: TreeNodeInfo | null = null): Promise<TreeNodeInfo[]> {
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
            currentNode = (currentNode.nodeData as any).parent as TreeNodeInfo | null;
        }
        return path;
    }
}

export default TauriFilesystemProvider; 