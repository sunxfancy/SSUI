import {useEffect, useState,useRef} from 'react';
import {Button, Tree, Icon, Popover, Menu, MenuItem, Dialog, FormGroup, InputGroup, Intent} from "@blueprintjs/core";
import { ContextMenu, ContextMenuItem } from 'ssui_components';
import { TauriFilesystemProvider, IFilesystemProvider, ExtendTreeNodeInfo } from '../../providers/FilesystemProvider';
import styles from './style.module.css'
import {TreeIcon} from "./TreeIcon.tsx";
import { useTranslation } from 'react-i18next';

import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import PropTypes from "prop-types";

interface WorkSpaceProps {
    currentWorkspace: string;
    onOpenWorkspace: () => void;
    onSelectWorkflow: () => void;
    onFileOpen: (path: string) => void;
    filesystemProvider?: IFilesystemProvider;
}

export const WorkSpace = (props: WorkSpaceProps) => {
    const { currentWorkspace, onOpenWorkspace, onSelectWorkflow } = props
    const [ fileTree, setFileTree ] = useState<ExtendTreeNodeInfo>()
    const [ contextMenu, setContextMenu ] = useState<{ x: number; y: number; node: ExtendTreeNodeInfo } | null>(null)
    const [ createDialog, setCreateDialog ] = useState<{ kind: 'file' | 'canvas'; parentNode: ExtendTreeNodeInfo | null } | null>(null)
    const [ deleteDialog, setDeleteDialog ] = useState<{ node: ExtendTreeNodeInfo } | null>(null)
    const [ inputName, setInputName ] = useState('')
    const [ inputError, setInputError ] = useState<string | null>(null)
    const [ busy, setBusy ] = useState(false)
    const filesystemProvider = useRef<IFilesystemProvider>(props.filesystemProvider || new TauriFilesystemProvider())
    const { t }= useTranslation();

    const mapChildNodes = (nodes: ExtendTreeNodeInfo[]): ExtendTreeNodeInfo[] =>
        nodes.map(c => ({
            ...c,
            icon: c.isFile ? <div className={styles.treeIcon}>{TreeIcon(c.id.toString())}</div> : 'folder-close'
        }));

    useEffect(() => {
        const fn = async () => {
            if (currentWorkspace) {
                const childNodes = await filesystemProvider.current.fetchFileTree(currentWorkspace, null);
                const lastword = currentWorkspace.split('/');
                setFileTree({
                    id: 0,
                    hasCaret: true,
                    label: lastword[lastword.length - 1],
                    isFile: false,
                    isExpanded: true,
                    icon: "folder-close",
                    nodeData: {
                        path: currentWorkspace
                    },
                    childNodes: mapChildNodes(childNodes)
                })
            }
        }
        fn()

    }, [currentWorkspace]);

    const handleNodeCollapse = (node: ExtendTreeNodeInfo) => {
        setFileTree(updateFileTree(fileTree as ExtendTreeNodeInfo, node.nodeData.path, { isExpanded: false }))
    }

    const handleNodeExpand = async (node: ExtendTreeNodeInfo) => {
        if (node.childNodes && node.childNodes.length === 0) {
            let childNodes = await filesystemProvider.current.fetchFileTree((node.nodeData as any).path as string, node);
            setFileTree(updateFileTree(fileTree as ExtendTreeNodeInfo, node.nodeData.path, { isExpanded: true, childNodes: mapChildNodes(childNodes) }))
        } else {
            setFileTree(updateFileTree(fileTree as ExtendTreeNodeInfo, node.nodeData.path, { isExpanded: true }))
        }
    }

    const handleNodeContextMenu = (node: ExtendTreeNodeInfo, _nodePath: number[], e: React.MouseEvent<HTMLElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setContextMenu({ x: e.clientX, y: e.clientY, node });
    }

    const closeContextMenu = () => setContextMenu(null)

    const refreshTree = async () => {
        if (!currentWorkspace) return;
        const childNodes = await filesystemProvider.current.fetchFileTree(currentWorkspace, null);
        setFileTree(prev => prev ? { ...prev, childNodes: mapChildNodes(childNodes) } : prev);
    }

    const refreshNode = async (node: ExtendTreeNodeInfo) => {
        if (node.isFile) {
            await refreshTree();
            return;
        }
        const childNodes = await filesystemProvider.current.fetchFileTree(node.nodeData.path, node);
        setFileTree(prev => prev ? updateFileTree(prev, node.nodeData.path, {
            isExpanded: true,
            childNodes: mapChildNodes(childNodes)
        }) : prev);
    }

    const copyPath = async (path: string) => {
        try {
            await navigator.clipboard.writeText(path);
        } catch (error) {
            console.error('复制路径失败:', error);
        }
    }

    const openCreateDialog = (parentNode: ExtendTreeNodeInfo | null, kind: 'file' | 'canvas') => {
        setInputName('');
        setInputError(null);
        setCreateDialog({ kind, parentNode });
    };

    const closeCreateDialog = () => {
        if (busy) return;
        setCreateDialog(null);
    };

    const confirmCreate = async () => {
        if (!createDialog || busy) return;
        const name = inputName.trim();
        if (!name) {
            setInputError(t('tree.nameRequired'));
            return;
        }
        setBusy(true);
        try {
            const { kind, parentNode } = createDialog;
            const dir = parentNode ? parentNode.nodeData.path : currentWorkspace;
            if (!dir) {
                setInputError(t('tree.createFailed'));
                return;
            }
            const createdPath = kind === 'canvas'
                ? await filesystemProvider.current.createCanvas(dir, name)
                : await filesystemProvider.current.createFile(dir, name);
            if (!createdPath) {
                setInputError(t('tree.createFailed'));
                return;
            }
            setCreateDialog(null);
            if (kind === 'canvas') {
                props.onFileOpen(createdPath);
            }
            if (parentNode) {
                await refreshNode(parentNode);
            } else {
                await refreshTree();
            }
        } finally {
            setBusy(false);
        }
    };

    const confirmDelete = async () => {
        if (!deleteDialog || busy) return;
        setBusy(true);
        try {
            const ok = await filesystemProvider.current.deletePath(deleteDialog.node.nodeData.path);
            setDeleteDialog(null);
            if (ok) {
                await refreshTree();
            }
        } finally {
            setBusy(false);
        }
    };

    const handleNodeClick = (node: ExtendTreeNodeInfo) => {
        // 先把所有节点的选择态清空
        setFileTree((prevState) => {
            const resetSelectedStatus = (node: ExtendTreeNodeInfo): ExtendTreeNodeInfo => {
                if (node.childNodes) {
                    return { ...node, isSelected: false, childNodes: node.childNodes.map(child => resetSelectedStatus(child))}
                }
                return { ...node, isSelected: false }
            }
            const resetedTree = resetSelectedStatus(prevState as ExtendTreeNodeInfo)
            return updateFileTree(resetedTree, node.nodeData.path, { isSelected: true })
        })

        if (node.childNodes == undefined && props.onFileOpen) {
            props.onFileOpen((node.nodeData as any).path as string);
        }
    }

    const updateFileTree = (tree: ExtendTreeNodeInfo, path: string, options: object)=>{
        if (path === tree.nodeData.path) {
            return { ...tree, ...options };
        }
        if (tree.childNodes && Array.isArray(tree.childNodes)) {
            const index = tree.childNodes.findIndex((child) => path.indexOf(child.nodeData.path) === 0);
            if (index !== -1) {
                const updatedChildren = [...tree.childNodes];
                updatedChildren[index] = updateFileTree(updatedChildren[index], path, options);
                return { ...tree, childNodes: updatedChildren, isSelected: false };
            }
        }

        return { ...tree, isSelected: false };
    }

    const buildContextMenuItems = (): ContextMenuItem[] => {
        if (!contextMenu) return [];
        const { node } = contextMenu;
        const items: ContextMenuItem[] = [];
        if (node.isFile) {
            items.push({
                label: t('tree.open'),
                icon: 'document-open' as const,
                onClick: () => props.onFileOpen(node.nodeData.path)
            });
        } else {
            items.push({
                label: t('tree.newFile'),
                icon: 'document' as const,
                onClick: () => openCreateDialog(node, 'file')
            });
            items.push({
                label: t('tree.newCanvas'),
                icon: 'media' as const,
                onClick: () => openCreateDialog(node, 'canvas')
            });
            items.push({ dividerBefore: true });
        }
        items.push(
            {
                label: t('tree.refresh'),
                icon: 'refresh' as const,
                onClick: () => refreshNode(node)
            },
            {
                label: t('tree.copyPath'),
                icon: 'clipboard' as const,
                onClick: () => copyPath(node.nodeData.path)
            },
            {
                label: t('tree.delete'),
                icon: 'trash' as const,
                intent: Intent.DANGER,
                onClick: () => setDeleteDialog({ node })
            }
        );
        return items;
    }

    return (
        <div className={styles.workspace}>
            <div className={styles.title}>
                <span className={styles.titleText}>{t('wsp')}</span>
                <span>
                    <Popover
                        content={
                            <Menu key="menu">
                                <MenuItem icon="folder-open" text={t('onw')} onClick={onOpenWorkspace} />
                                <MenuItem icon="generate" text={t('sfpw')} onClick={onSelectWorkflow} />
                                <MenuItem icon="document" text={t('tree.newFile')} onClick={() => openCreateDialog(null, 'file')} />
                                <MenuItem icon="media" text={t('tree.newCanvas')} onClick={() => openCreateDialog(null, 'canvas')} />
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
            {currentWorkspace && fileTree ? (
                <div className={styles.treeWp}>
                    {/*@ts-ignore*/}
                    <Tree
                        contents={[fileTree]}
                        onNodeExpand={handleNodeExpand}
                        onNodeCollapse={handleNodeCollapse}
                        onNodeClick={handleNodeClick}
                        onNodeContextMenu={handleNodeContextMenu}
                        className={styles.tree}
                    />
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column',  padding: '20px', height: '100%' }}>
                    <p>{t('nodyc')}</p>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '20px' }} >
                        <Button onClick={onOpenWorkspace} icon="folder-open" size="large" variant="solid">{t('onw')}</Button>
                    </div>
                    <p>{t('ocapw')}</p>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '10px' }} >
                        <Button onClick={onSelectWorkflow} icon="generate" size="large" variant="solid">{t('sfpw')}</Button>
                    </div>
                </div>
            )}
            {contextMenu && (
                <ContextMenu
                    x={contextMenu.x}
                    y={contextMenu.y}
                    items={buildContextMenuItems()}
                    onClose={closeContextMenu}
                />
            )}
            <Dialog
                isOpen={createDialog !== null}
                onClose={closeCreateDialog}
                title={createDialog?.kind === 'canvas' ? t('tree.createCanvasTitle') : t('tree.createFileTitle')}
            >
                <div style={{ padding: '20px' }}>
                    <FormGroup label={t('tree.name')} labelFor="tree-input-name">
                        <InputGroup
                            id="tree-input-name"
                            autoFocus
                            placeholder={createDialog?.kind === 'canvas' ? t('tree.canvasNamePlaceholder') : t('tree.fileNamePlaceholder')}
                            value={inputName}
                            onChange={(e) => {
                                setInputName(e.target.value);
                                setInputError(null);
                            }}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') confirmCreate();
                            }}
                            intent={inputError ? Intent.DANGER : Intent.NONE}
                        />
                        {inputError && <div style={{ color: 'red', marginTop: '5px' }}>{inputError}</div>}
                    </FormGroup>
                </div>
                <div className="bp5-dialog-footer">
                    <Button onClick={closeCreateDialog} disabled={busy}>{t('tree.cancel')}</Button>
                    <Button intent={Intent.PRIMARY} onClick={confirmCreate} loading={busy}>{t('tree.create')}</Button>
                </div>
            </Dialog>
            <Dialog
                isOpen={deleteDialog !== null}
                onClose={() => { if (!busy) setDeleteDialog(null); }}
                title={t('tree.deleteConfirmTitle')}
            >
                <div style={{ padding: '20px' }}>
                    <p>{t('tree.deleteConfirmMessage', { name: deleteDialog?.node.label || '' })}</p>
                </div>
                <div className="bp5-dialog-footer">
                    <Button onClick={() => setDeleteDialog(null)} disabled={busy}>{t('tree.cancel')}</Button>
                    <Button intent={Intent.DANGER} onClick={confirmDelete} loading={busy}>{t('tree.delete')}</Button>
                </div>
            </Dialog>
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
