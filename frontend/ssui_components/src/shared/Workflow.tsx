import React from 'react';
import { createRoot } from 'react-dom/client';
import { NodeEditor, ClassicPreset } from 'rete';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { ReactPlugin, Presets as ReactPresets, useRete } from 'rete-react-plugin';
import {
    ConnectionPlugin,
    Presets as ConnectionPresets,
} from "rete-connection-plugin";
import { ContextMenuPlugin } from "rete-context-menu-plugin";

import {
    AreaExtra,
    BaseNode,
    ButtonControl,
    ButtonControlRender,
    Connection,
    FunctionCallNode,
    FunctionDefinitionNode,
    FunctionDefinitionRender,
    InputNode,
    InputNodeRender,
    NameControl,
    NameControlRender,
    OperatorNode,
    OutputNode,
    OutputNodeRender,
    InfoControl,
    InfoControlRender,
    Schemes,
} from './Nodes';
import './Workflow.css';

export interface WorkflowProps {
    path: string;
}

const createEditor = async (container: HTMLElement) => {
    console.log("初始化工作流编辑器");

    const editor = new NodeEditor<Schemes>();
    const area = new AreaPlugin<Schemes, AreaExtra>(container);
    const connection = new ConnectionPlugin<Schemes, AreaExtra>();
    const reactRender = new ReactPlugin<Schemes, AreaExtra>({ createRoot });

    const addNode = async (node: BaseNode) => {
        await editor.addNode(node);
        await area.translate(node.id, area.area.pointer);
    };

    const syncDefinitions = () => {
        for (const node of editor.getNodes()) {
            if (node instanceof FunctionDefinitionNode) {
                node.sync();
            }
        }
    };

    // 创建函数定义：有选中节点时按选中节点生成包围框，否则创建空框
    const createDefinition = async () => {
        const def = new FunctionDefinitionNode(area);
        await editor.addNode(def);
        const selected = editor.getNodes().filter((n) => n.selected && n !== def);
        if (selected.length > 0) {
            def.fitToNodes(selected);
        } else {
            await area.translate(def.id, area.area.pointer);
        }
        syncDefinitions();
    };

    const contextMenu = new ContextMenuPlugin<Schemes>({
        items: (context) => {
            if (context === 'root') {
                const definitions = editor.getNodes().filter(
                    (n): n is FunctionDefinitionNode => n instanceof FunctionDefinitionNode
                );
                return {
                    searchBar: true,
                    list: [
                        { label: '输入节点', key: 'input', handler: () => addNode(new InputNode(area)) },
                        { label: '返回节点', key: 'output', handler: () => addNode(new OutputNode(area)) },
                        { label: '算子节点', key: 'operator', handler: () => addNode(new OperatorNode('算子')) },
                        { label: '函数定义（框选节点）', key: 'definition', handler: () => createDefinition() },
                        {
                            label: '函数调用',
                            key: 'call',
                            handler: async () => {
                                // 无子菜单时的兜底：直接调用第一个函数定义
                                const def = editor.getNodes().find(
                                    (n): n is FunctionDefinitionNode => n instanceof FunctionDefinitionNode
                                );
                                if (def) await addNode(new FunctionCallNode(area, def));
                            },
                            subitems: definitions.length > 0
                                ? definitions.map((d) => ({
                                    label: d.label,
                                    key: d.id,
                                    handler: () => addNode(new FunctionCallNode(area, d)),
                                }))
                                : [{ label: '（请先创建函数定义）', key: 'no-def', handler: async () => {} }],
                        },
                    ],
                };
            }

            // 节点 / 连线：删除
            return {
                searchBar: false,
                list: [{
                    label: 'Delete',
                    key: 'delete',
                    handler: async () => {
                        if ('source' in context && 'target' in context) {
                            await editor.removeConnection(context.id);
                            return;
                        }
                        for (const c of editor.getConnections()) {
                            if (c.source === context.id || c.target === context.id) {
                                await editor.removeConnection(c.id);
                            }
                        }
                        await editor.removeNode(context.id);
                    },
                }],
            };
        },
    });

    // Shift + 点击多选，拖拽时所有选中的节点一起移动
    let shiftDown = false;
    const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Shift') shiftDown = true;
    };
    const onKeyUp = (e: KeyboardEvent) => {
        if (e.key === 'Shift') shiftDown = false;
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);

    // 拖动已选中的节点时保持多选（多选后直接拖动即可整组移动，不必一直按 Shift）
    let keepMultiSelection = false;
    area.addPipe((context) => {
        if (context && typeof context === 'object' && 'type' in context) {
            const type = (context as { type: string }).type;
            if (type === 'nodepicked') {
                const id = (context as { data?: { id?: string } }).data?.id;
                const node = id ? editor.getNode(id) : undefined;
                keepMultiSelection = node?.selected === true;
            }
        }
        return context;
    });

    AreaExtensions.selectableNodes(area, AreaExtensions.selector(), {
        accumulating: {
            active: () => shiftDown || keepMultiSelection,
        },
    });

    connection.addPreset(ConnectionPresets.classic.setup());
    reactRender.addPreset(ReactPresets.contextMenu.setup());

    // 注册自定义节点组件
    reactRender.addPreset(ReactPresets.classic.setup({
        customize: {
            node(context) {
                if (context.payload instanceof FunctionDefinitionNode) {
                    return FunctionDefinitionRender;
                }
                if (context.payload instanceof InputNode) {
                    return InputNodeRender;
                }
                if (context.payload instanceof OutputNode) {
                    return OutputNodeRender;
                }
                return ReactPresets.classic.Node;
            },
            control(context) {
                if (context.payload instanceof ButtonControl) {
                    return ButtonControlRender;
                }
                if (context.payload instanceof NameControl) {
                    return NameControlRender;
                }
                if (context.payload instanceof InfoControl) {
                    return InfoControlRender;
                }
                if (context.payload instanceof ClassicPreset.InputControl) {
                    return ReactPresets.classic.Control;
                }
                return null;
            }
        }
    }));

    // 配置插件
    editor.use(area);
    area.use(connection);
    area.use(contextMenu);
    area.use(reactRender);
    AreaExtensions.simpleNodesOrder(area);

    // 右键前选中的节点快照：右键会清空选中，菜单打开前恢复，便于“框选节点生成函数”
    let rightClickSelection: string[] = [];

    // 节点/矩形移动、增删、重渲染时，重算函数定义框内的成员
    area.addPipe((context) => {
        if (context && typeof context === 'object' && 'type' in context) {
            const type = (context as { type: string }).type;
            if (type === 'pointerdown') {
                const event = (context as { data?: { event?: PointerEvent } }).data?.event;
                if (event?.button === 2) {
                    rightClickSelection = editor.getNodes()
                        .filter((n) => n.selected)
                        .map((n) => n.id);
                }
            }
            if (type === 'contextmenu') {
                rightClickSelection.forEach((id) => {
                    const node = editor.getNode(id);
                    if (node && !node.selected) {
                        node.selected = true;
                        void area.update('node', id);
                    }
                });
            }
            if (type === 'nodetranslated') {
                // 拖动函数定义框时，框内节点一起移动
                const data = (context as {
                    data?: { id: string; position?: { x: number; y: number }; previous?: { x: number; y: number } };
                }).data;
                const node = data?.id ? editor.getNode(data.id) : undefined;
                if (node instanceof FunctionDefinitionNode && data?.position && data.previous) {
                    const dx = data.position.x - data.previous.x;
                    const dy = data.position.y - data.previous.y;
                    if (dx !== 0 || dy !== 0) {
                        for (const member of editor.getNodes()) {
                            if (member === node) continue;
                            if (!node.isNodeInside(member)) continue;
                            const view = area.nodeViews.get(member.id);
                            if (view) {
                                void view.translate(view.position.x + dx, view.position.y + dy);
                            }
                        }
                    }
                }
            }
            if (
                type === 'render' ||
                type === 'nodetranslated' ||
                type === 'nodecreated' ||
                type === 'noderemoved'
            ) {
                syncDefinitions();
            }
            if (type === 'render') {
                // 函数定义框始终渲染在其它节点下层
                const renderData = (context as { data?: { type?: string; element?: HTMLElement; payload?: unknown } }).data;
                if (
                    renderData?.type === 'node' &&
                    renderData.payload instanceof FunctionDefinitionNode &&
                    renderData.element
                ) {
                    const holder = area.area.content.holder;
                    if (holder.firstChild !== renderData.element) {
                        holder.insertBefore(renderData.element, holder.firstChild);
                    }
                }
            }
        }
        return context;
    });

    // 示例流程：一个函数定义框把 输入 → 算子 → 返回 框起来，
    // 框外的 输入/返回 节点通过函数调用节点使用该函数
    const definitionNode = new FunctionDefinitionNode(area, '图像生成');
    definitionNode.boxWidth = 900;
    definitionNode.boxHeight = 340;

    const innerInput = new InputNode(area);
    innerInput.addParameter();
    innerInput.addParameter();
    const operator = new OperatorNode('采样');
    const innerOutput = new OutputNode(area);
    innerOutput.addReturn();
    innerOutput.addReturn();

    const callNode = new FunctionCallNode(area, definitionNode);

    const topInput = new InputNode(area);
    topInput.addParameter();
    topInput.addParameter();
    const topOutput = new OutputNode(area);
    topOutput.addReturn();
    topOutput.addReturn();

    await editor.addNode(definitionNode);
    await editor.addNode(innerInput);
    await editor.addNode(operator);
    await editor.addNode(innerOutput);
    await editor.addNode(callNode);
    await editor.addNode(topInput);
    await editor.addNode(topOutput);

    await area.translate(definitionNode.id, { x: -560, y: 20 });
    await area.translate(innerInput.id, { x: -520, y: 150 });
    await area.translate(operator.id, { x: -250, y: 180 });
    await area.translate(innerOutput.id, { x: 20, y: 150 });
    await area.translate(callNode.id, { x: 520, y: 200 });
    await area.translate(topInput.id, { x: -1040, y: 250 });
    await area.translate(topOutput.id, { x: 840, y: 250 });

    // 连接示例：顶层输入参数 → 函数调用 → 顶层返回
    await editor.addConnection(new Connection<BaseNode, BaseNode>(topInput, 'param_0', callNode, 'in_param_0'));
    await editor.addConnection(new Connection<BaseNode, BaseNode>(topInput, 'param_1', callNode, 'in_param_1'));
    await editor.addConnection(new Connection<BaseNode, BaseNode>(callNode, 'out_return_0', topOutput, 'return_0'));
    await editor.addConnection(new Connection<BaseNode, BaseNode>(callNode, 'out_return_1', topOutput, 'return_1'));

    syncDefinitions();

    setTimeout(() => {
        AreaExtensions.zoomAt(area, editor.getNodes());
    }, 1);

    // 工具栏：方便添加节点
    const toolbar = document.createElement('div');
    toolbar.className = 'workflow-toolbar';
    const addToolbarButton = (label: string, handler: () => void | Promise<void>) => {
        const button = document.createElement('button');
        button.className = 'workflow-toolbar-button';
        button.textContent = label;
        button.addEventListener('pointerdown', (e) => e.stopPropagation());
        button.addEventListener('contextmenu', (e) => e.stopPropagation());
        button.addEventListener('click', () => void handler());
        toolbar.appendChild(button);
    };
    addToolbarButton('添加输入节点', () => addNode(new InputNode(area)));
    addToolbarButton('添加返回节点', () => addNode(new OutputNode(area)));
    addToolbarButton('添加算子节点', () => addNode(new OperatorNode('算子')));
    addToolbarButton('添加函数定义', () => createDefinition());
    const callButton = document.createElement('button');
    callButton.className = 'workflow-toolbar-button';
    callButton.textContent = '添加函数调用';
    callButton.addEventListener('pointerdown', (e) => e.stopPropagation());
    callButton.addEventListener('click', async () => {
        const def = editor.getNodes().find(
            (n): n is FunctionDefinitionNode => n instanceof FunctionDefinitionNode
        );
        if (!def) {
            console.warn('请先创建函数定义，再添加函数调用');
            return;
        }
        await addNode(new FunctionCallNode(area, def));
    });
    toolbar.appendChild(callButton);
    const clearButton = document.createElement('button');
    clearButton.className = 'workflow-toolbar-button workflow-toolbar-clear';
    clearButton.textContent = '清空画布';
    clearButton.addEventListener('pointerdown', (e) => e.stopPropagation());
    clearButton.addEventListener('click', () => void editor.clear());
    toolbar.appendChild(clearButton);
    container.appendChild(toolbar);

    return {
        destroy: () => {
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('keyup', onKeyUp);
            toolbar.remove();
            area.destroy();
        },
    };
};

export const Workflow: React.FC<WorkflowProps> = ({ path }) => {
    const [ref, editor] = useRete(createEditor)
    return (
        <div className="workflow-ui" style={{ width: '100%', height: '100vh', position: 'relative' }}>
            <div ref={ref} style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} />
        </div>
    );
};

