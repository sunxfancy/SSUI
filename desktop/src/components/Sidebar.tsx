import React, { Component } from 'react';
import { Tree, TreeNodeInfo } from "@blueprintjs/core";
import { open } from '@tauri-apps/plugin-dialog';
import { readDir, BaseDirectory } from '@tauri-apps/plugin-fs';
import { join } from '@tauri-apps/api/path';


class Sidebar extends Component<{
    currentWorkspace: string | null,
    onOpenWorkspace?: (workspace: string) => void
}, { fileTree: TreeNodeInfo[] }> {
    constructor(props: Sidebar['props']) {
        super(props);
        this.state = {
            fileTree: []
        };
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

    async fetchFileTree(directory: string) {
        try {
            const files = await readDir(directory);
            console.log(files);
            return await Promise.all(files.map(async (file) => ({
                id: file.name,
                label: file.name,
                isFile: !file.isDirectory,
                nodeData: { path: await join(directory, file.name)},
                childNodes: file.isDirectory ? [] : undefined
            })));
        } catch (error) {
            console.error("Error reading directory:", error);
            return [];
        }
    }

    updateFileTreeWithChildren(parent: TreeNodeInfo, childNodes: TreeNodeInfo[]) {
        let path = (parent.nodeData as any).path as string;
        let dirs = path.split("\\");
        
        this.setState(state => {
            const fileTree = state.fileTree.map(n =>
                n.id === parent.id ? { ...n, childNodes, isExpanded: true } : n
            );
            return { fileTree };
        });



    }

    handleNodeExpand = async (node: TreeNodeInfo) => {
        console.log('handleNodeExpand', node);
        if (node.childNodes && node.childNodes.length === 0) {
            const childNodes = await this.fetchFileTree((node.nodeData as any).path as string);
            this.updateFileTreeWithChildren(node, childNodes);
        } else {
            this.setState(state => {
                const fileTree = state.fileTree.map(n =>
                    n.id === node.id ? { ...n, isExpanded: false } : n
                );
                return { fileTree };
            });
        }
    }


    handleNodeCollapse = (node: TreeNodeInfo) => {
        console.log('handleNodeCollapse', node);
        node.isExpanded = false;
        this.forceUpdate();
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