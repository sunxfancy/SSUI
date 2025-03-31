import { Component } from 'react';
import { Button, Tree, TreeNodeInfo } from "@blueprintjs/core";
import { TauriFilesystemProvider, IFilesystemProvider } from '../services/FilesystemProvider';

import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";

export class Sidebar extends Component<{
    currentWorkspace: string | null,
    onOpenWorkspace?: () => void,
    onSelectWorkflow?: () => void,
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
                    <div style={{ display: 'flex', flexDirection: 'column',  justifyContent: 'center', padding: '20px', height: '100%' }}>
                        <p>当前没有打开的目录, 您可以：</p>
                        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '20px' }} >
                            <Button onClick={this.props.onOpenWorkspace} icon="folder-open" size="large" variant="solid">打开已有工作空间</Button>
                        </div>
                        <p>或者，选择我们准备的预制工作流：</p>
                        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '10px' }} >
                            <Button onClick={this.props.onSelectWorkflow} icon="generate" size="large" variant="solid">从预制工作流开始</Button>
                        </div>
                    </div>
                )}
            </div>
        );
    }
}

export default Sidebar;