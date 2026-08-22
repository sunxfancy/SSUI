import { TreeNodeInfo } from "@blueprintjs/core";
import { IFilesystemProvider, ExtendTreeNodeInfo } from "../providers/FilesystemProvider";

export class MockFilesystemProvider implements IFilesystemProvider {
    private mockFileSystem: Map<string, ExtendTreeNodeInfo[]> = new Map();
    private idCounter: number = 0;

    constructor() {
        // 初始化模拟文件系统结构
        this.initMockFileSystem();
    }

    private initMockFileSystem() {
        // 模拟根目录
        const rootFiles = [
            {
                id: "src",
                label: "src",
                isFile: false,
                nodeData: { path: "/src", parent: null },
                childNodes: []
            },
            {
                id: "public",
                label: "public",
                isFile: false,
                nodeData: { path: "/public", parent: null },
                childNodes: []
            },
            {
                id: "package.json",
                label: "package.json",
                isFile: true,
                nodeData: { path: "/package.json", parent: null }
            },
            {
                id: "README.md",
                label: "README.md",
                isFile: true,
                nodeData: { path: "/README.md", parent: null }
            }
        ];
        this.mockFileSystem.set("/", rootFiles);

        // 模拟 src 目录
        const srcFiles = [
            {
                id: "components",
                label: "components",
                isFile: false,
                nodeData: { path: "/src/components", parent: rootFiles[0] },
                childNodes: []
            },
            {
                id: "services",
                label: "services",
                isFile: false,
                nodeData: { path: "/src/services", parent: rootFiles[0] },
                childNodes: []
            },
            {
                id: "App.tsx",
                label: "App.tsx",
                isFile: true,
                nodeData: { path: "/src/App.tsx", parent: rootFiles[0] }
            },
            {
                id: "index.tsx",
                label: "index.tsx",
                isFile: true,
                nodeData: { path: "/src/index.tsx", parent: rootFiles[0] }
            }
        ];
        this.mockFileSystem.set("/src", srcFiles);

        // 模拟 src/components 目录
        const componentsFiles = [
            {
                id: "Sidebar.tsx",
                label: "Sidebar.tsx",
                isFile: true,
                nodeData: { path: "/src/components/Sidebar.tsx", parent: srcFiles[0] }
            },
            {
                id: "FileTree.tsx",
                label: "FileTree.tsx",
                isFile: true,
                nodeData: { path: "/src/components/FileTree.tsx", parent: srcFiles[0] }
            }
        ];
        this.mockFileSystem.set("/src/components", componentsFiles);

        // 模拟 src/services 目录
        const servicesFiles = [
            {
                id: "FilesystemProvider.ts",
                label: "FilesystemProvider.ts",
                isFile: true,
                nodeData: { path: "/src/services/FilesystemProvider.ts", parent: srcFiles[1] }
            },
            {
                id: "MockFilesystemProvider.ts",
                label: "MockFilesystemProvider.ts",
                isFile: true,
                nodeData: { path: "/src/services/MockFilesystemProvider.ts", parent: srcFiles[1] }
            }
        ];
        this.mockFileSystem.set("/src/services", servicesFiles);

        // 模拟 public 目录
        const publicFiles = [
            {
                id: "index.html",
                label: "index.html",
                isFile: true,
                nodeData: { path: "/public/index.html", parent: rootFiles[1] }
            },
            {
                id: "favicon.ico",
                label: "favicon.ico",
                isFile: true,
                nodeData: { path: "/public/favicon.ico", parent: rootFiles[1] }
            }
        ];
        this.mockFileSystem.set("/public", publicFiles);
        console.log(this.mockFileSystem);
    }

    public async fetchFileTree(directory: string, parent: ExtendTreeNodeInfo | null = null): Promise<ExtendTreeNodeInfo[]> {
        console.log('fetchFileTree', directory, parent);
        // 模拟异步行为
        return new Promise((resolve) => {
            setTimeout(() => {
                let files = this.mockFileSystem.get(directory) || [];
                console.log('files', files);
                resolve(files);
            }, 10);
        });
    }

    public getPathToRoot(node: TreeNodeInfo): string[] {
        const path = [];
        let currentNode: TreeNodeInfo | null = node;
        while (currentNode) {
            path.unshift(currentNode.id as string);
            currentNode = (currentNode.nodeData as any).parent as TreeNodeInfo | null;
        }
        return path;
    }

    private async addMockNode(parentPath: string, name: string): Promise<string | null> {
        const fullPath = `${parentPath}/${name}`;
        const files = this.mockFileSystem.get(parentPath);
        if (!files) {
            return null;
        }
        if (files.some(f => f.label === name)) {
            return null;
        }
        this.idCounter += 1;
        const nodeData = { path: fullPath, parent: null };
        const node: ExtendTreeNodeInfo = {
            id: `mock-${this.idCounter}`,
            label: name,
            isFile: true,
            nodeData
        };
        files.push(node);
        return fullPath;
    }

    public async createFile(parentPath: string, name: string): Promise<string | null> {
        return this.addMockNode(parentPath, name);
    }

    public async createCanvas(parentPath: string, name: string): Promise<string | null> {
        const canvasName = name.trim().endsWith('.canvas') ? name.trim() : `${name.trim()}.canvas`;
        return this.addMockNode(parentPath, canvasName);
    }

    public async deletePath(path: string): Promise<boolean> {
        for (const files of this.mockFileSystem.values()) {
            const index = files.findIndex(f => f.nodeData.path === path);
            if (index !== -1) {
                files.splice(index, 1);
                return true;
            }
        }
        return false;
    }
}

export default MockFilesystemProvider;
