import {useEffect, useState,useRef} from 'react';
import {Button, Tree, TreeNodeInfo, Icon, Popover, Menu, MenuItem} from "@blueprintjs/core";
import { TauriFilesystemProvider, IFilesystemProvider } from '../../providers/FilesystemProvider';
import styles from './style.module.css'
import {TreeIcon} from "./TreeIcon.tsx";

import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import PropTypes from "prop-types";

export const WorkSpace = (props) => {
    const { currentWorkspace, onOpenWorkspace, onSelectWorkflow, onFileOpen } = props
    const [ fileTree, setFileTree ] = useState([])
    const filesystemProvider = useRef<IFilesystemProvider>(props.filesystemProvider || new TauriFilesystemProvider())

    useEffect(() => {
        const fn = async () => {
            console.log('filesystemProvider.current触发')
            if (currentWorkspace) {
                const childNodes = await filesystemProvider.current.fetchFileTree(currentWorkspace, null);
                const lastword = currentWorkspace.split('/');
                setFileTree([
                    {
                        id: 0,
                        hasCaret: true,
                        label: lastword[lastword.length - 1],
                        isExpanded: true,
                        icon: "folder-close",
                        childNodes: childNodes.map(c => ({
                            ...c,
                            icon: <div className={styles.treeIcon}>{GetIcon(c.id)}</div>
                        }))
                    }
                ])
            }
        }
        fn()

    }, [currentWorkspace]);

    const GetIcon = (id: string) => {
        const extArr = id.split('.')
        const ext = extArr[extArr.length - 1]
        return TreeIcon(ext)
    }

    const handleNodeCollapse = (node: TreeNodeInfo) => {
        updateFileTreeWithChildren(node, false, undefined)
    }

    const handleNodeExpand = async (node: TreeNodeInfo) => {
        if (node.childNodes && node.childNodes.length === 0) {
            const childNodes = await filesystemProvider.current.fetchFileTree((node.nodeData as any).path as string, node);
            updateFileTreeWithChildren(node, true, childNodes);
        } else {
            updateFileTreeWithChildren(node, true, undefined);
        }
    }

    const handleNodeClick = (node: TreeNodeInfo) => {
        if (node.childNodes == undefined && props.onFileOpen) {
            props.onFileOpen((node.nodeData as any).path as string);
        }
    }

    const updateFileTreeWithChildren = (node: TreeNodeInfo, isExpanded: boolean, childNodes: TreeNodeInfo[] | undefined) => {
        const path = filesystemProvider.current.getPathToRoot(node);

        const updateChildNodes = (nodes: TreeNodeInfo[], path: string[]): TreeNodeInfo[] => {
            if (path.length === 0) return nodes;

            return nodes.map(n => {
                if (n.id === path[0]) {
                    if (path.length === 1) {
                        if (childNodes) {
                            return {...n, childNodes, isExpanded};
                        } else {
                            return {...n, isExpanded};
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

        setFileTree(updateChildNodes(fileTree, path));

    }

    return (
        <div className={styles.workspace}>
            <div className={styles.title}>
                <span className={styles.titleText}>工作空间</span>
                <span>
                    <Popover
                        content={
                            <Menu key="menu">
                                <MenuItem icon="folder-open" text="打开新的已有工作空间" onClick={onOpenWorkspace} />
                                <MenuItem icon="generate" text="从预制工作流开始" onClick={onSelectWorkflow} />
                            </Menu>
                        }
                        position="bottom-right"
                    >
                        {
                            currentWorkspace &&
                            <div className={styles.addBtn}>
                                <Icon icon="plus"></Icon>
                            </div>
                        }
                    </Popover>

                </span>
            </div>
            {currentWorkspace ? (
                <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
                    <Tree
                        contents={fileTree}
                        onNodeExpand={handleNodeExpand}
                        onNodeCollapse={handleNodeCollapse}
                        onNodeClick={handleNodeClick}
                        className={styles.tree}
                    />
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column',  padding: '20px', height: '100%' }}>
                    <p>当前没有打开的目录, 您可以：</p>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '20px' }} >
                        <Button onClick={onOpenWorkspace} icon="folder-open" size="large" variant="solid">打开已有工作空间</Button>
                    </div>
                    <p>或者，选择我们准备的预制工作流：</p>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '10px' }} >
                        <Button onClick={onSelectWorkflow} icon="generate" size="large" variant="solid">从预制工作流开始</Button>
                    </div>
                </div>
            )}
        </div>
    )
}

WorkSpace.propTypes = {
    currentWorkspace: PropTypes.string,
    onOpenWorkspace: PropTypes.func,
    onSelectWorkflow: PropTypes.func,
    onFileOpen: PropTypes.func,
    filesystemProvider: PropTypes.object
}
