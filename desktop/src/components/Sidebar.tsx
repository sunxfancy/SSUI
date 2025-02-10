import React, { Component } from 'react';
import { Tree, TreeNodeInfo } from "@blueprintjs/core";
import { open } from '@tauri-apps/plugin-dialog';
import { readDir, BaseDirectory } from '@tauri-apps/plugin-fs';
import { join } from '@tauri-apps/api/path';


class Sidebar extends Component<{
    currentWorkspace: string | null,
    onOpenWorkspace?: (workspace: string) => void,
    onFileOpen?: (filePath: string) => void
}, { fileTree: TreeNodeInfo[] }> {
    ignoredPaths: string[];
    constructor(props: Sidebar['props']) {
        super(props);
        this.state = {
            fileTree: []
        };

        this.ignoredPaths = [
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
    }

    componentDidMount() {
        if (this.props.currentWorkspace) {
            this.fetchFileTree(this.props.currentWorkspace);
        }
    }

    componentDidUpdate(prevProps: Sidebar['props']) {
        if (prevProps.currentWorkspace !== this.props.currentWorkspace && this.props.currentWorkspace) {
            this.fetchFileTree(this.props.currentWorkspace);
        }
    }

    async fetchFileTree(directory: string, parent: TreeNodeInfo | null = null) {
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

    updateFileTreeWithChildren(node: TreeNodeInfo, isExpanded: boolean, childNodes: TreeNodeInfo[] | undefined) {
        const path = this.getPathToRoot(node);
        console.log('updateFileTreeWithChildren', node, isExpanded, childNodes, path);
        const updateChildNodes = (nodes: TreeNodeInfo[], path: string[]): TreeNodeInfo[] => {
            if (path.length === 0) return nodes;

            return nodes.map(n => {
                if (n.id === path[0]) {
                    if (path.length === 1) {
                        if (childNodes) {
                            return { ...n, childNodes, isExpanded };
                        } else {
                            return { ...n, isExpanded };
                        }
                    } else {
                        return {
                            ...n,
                            childNodes: n.childNodes ? updateChildNodes(n.childNodes, path.slice(1)) : n.childNodes
                        };
                    }
                }
                return n;
            });
        };

        this.setState(state => {
            const fileTree = updateChildNodes(state.fileTree, path);
            return { fileTree };
        });
    }

    handleNodeExpand = async (node: TreeNodeInfo) => {
        console.log('handleNodeExpand', node);
        if (node.childNodes && node.childNodes.length === 0) {
            const childNodes = await this.fetchFileTree((node.nodeData as any).path as string, node);
            this.updateFileTreeWithChildren(node, true, childNodes);
        } else {
            this.updateFileTreeWithChildren(node, true, undefined);
        }
    }


    handleNodeCollapse = (node: TreeNodeInfo) => {
        this.updateFileTreeWithChildren(node, false, undefined);
    }

    handleNodeClick = (node: TreeNodeInfo) => {
        console.log('handleNodeClick', node);
        if (node.childNodes == undefined && this.props.onFileOpen) {
            this.props.onFileOpen((node.nodeData as any).path as string);
        }
    }

    render() {
        const { currentWorkspace, onOpenWorkspace } = this.props;
        const { fileTree } = this.state;

        return (
            <div className="sidebar">
                {currentWorkspace ? (
                    <Tree
                        contents={fileTree}
                        onNodeExpand={this.handleNodeExpand}
                        onNodeCollapse={this.handleNodeCollapse}
                        onNodeClick={this.handleNodeClick}
                    />
                ) : (
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '30px' }}>
                        <button onClick={() => {
                            const options = {
                                directory: true,
                                multiple: false
                            };
                            open(options).then(async (result: string | null) => {
                                if (result && onOpenWorkspace) {
                                    onOpenWorkspace(result);
                                    const childNodes = await this.fetchFileTree(result);
                                    this.setState({ fileTree: childNodes });
                                }
                            });

                        }}>打开工作空间</button>

                    </div>
                )}
            </div>
        );
    }
}

export default Sidebar;