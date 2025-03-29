import { Component } from 'react';
import { Tree, TreeNodeInfo } from "@blueprintjs/core";
import { open } from '@tauri-apps/plugin-dialog';
import { TauriFilesystemProvider, IFilesystemProvider } from '../services/FilesystemProvider';

import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";

export class Sidebar extends Component<{
    currentWorkspace: string | null,
    onOpenWorkspace?: (workspace: string) => void,
    onFileOpen?: (filePath: string) => void,
    filesystemProvider?: IFilesystemProvider,
}, { fileTree: TreeNodeInfo[] }> {
    filesystemProvider: IFilesystemProvider;
    
    constructor(props: Sidebar['props']) {
        super(props);
        this.state = {
            fileTree: []
        };
        if (this.props.filesystemProvider) {
            this.filesystemProvider = this.props.filesystemProvider;
        } else {
            this.filesystemProvider = new TauriFilesystemProvider();
        }
    }

    async componentDidMount() {
        if (this.props.currentWorkspace) {
            const childNodes = await this.fetchFileTree(this.props.currentWorkspace);
            this.setState({ fileTree: childNodes });
        }
    }

    async componentDidUpdate(prevProps: Sidebar['props']) {
        if (prevProps.currentWorkspace !== this.props.currentWorkspace && this.props.currentWorkspace) {
            const childNodes = await this.fetchFileTree(this.props.currentWorkspace);
            this.setState({ fileTree: childNodes });
        }
    }

    async fetchFileTree(directory: string, parent: TreeNodeInfo | null = null) {
        return await this.filesystemProvider.fetchFileTree(directory, parent);
    }

    updateFileTreeWithChildren(node: TreeNodeInfo, isExpanded: boolean, childNodes: TreeNodeInfo[] | undefined) {
        const path = this.filesystemProvider.getPathToRoot(node);
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

    handleOpenWorkspaceBtn = () => {
        const options = {
            directory: true,
            multiple: false
        };
        const onOpenWorkspace = this.props.onOpenWorkspace;
        open(options).then(async (result: string | null) => {
            if (result && onOpenWorkspace) {
                onOpenWorkspace(result);
            }
        });
    }

    render() {
        const { currentWorkspace } = this.props;
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
                            <button onClick={this.handleOpenWorkspaceBtn}>打开工作空间</button>
                    </div>
                )}
            </div>
        );
    }
}

export default Sidebar;