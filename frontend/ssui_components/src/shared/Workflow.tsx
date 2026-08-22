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
    NameControl,
    NameControlRender,
    OutputNode,
    ParameterControl,
    ParameterControlRender,
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
                        { label: '函数定义', key: 'definition', handler: () => addNode(new FunctionDefinitionNode(area)) },
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

    // 使用 AreaExtensions 来配置插件
    AreaExtensions.selectableNodes(area, AreaExtensions.selector(), {
        accumulating: AreaExtensions.accumulateOnCtrl()
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
                return ReactPresets.classic.Node;
            },
            control(context) {
                if (context.payload instanceof ButtonControl) {
                    return ButtonControlRender;
                }
                if (context.payload instanceof ParameterControl) {
                    return ParameterControlRender;
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

    // 添加示例流程：输入 → 函数调用（引用函数定义）→ 返回
    const inputNode = new InputNode(area);
    const definitionNode = new FunctionDefinitionNode(area, '图像生成');
    const callNode = new FunctionCallNode(area, definitionNode);
    const outputNode = new OutputNode(area);

    inputNode.addParameter();
    inputNode.addParameter();
    definitionNode.addParameter();
    definitionNode.addReturn();
    outputNode.addReturn();
    outputNode.addReturn();

    await editor.addNode(inputNode);
    await editor.addNode(definitionNode);
    await editor.addNode(callNode);
    await editor.addNode(outputNode);

    // 连接示例：输入参数 → 函数调用 → 返回
    await editor.addConnection(new Connection<BaseNode, BaseNode>(inputNode, 'param_0', callNode, 'in_param_0'));
    await editor.addConnection(new Connection<BaseNode, BaseNode>(inputNode, 'param_1', callNode, 'in_param_1'));
    await editor.addConnection(new Connection<BaseNode, BaseNode>(callNode, 'out_return_0', outputNode, 'return_0'));
    await editor.addConnection(new Connection<BaseNode, BaseNode>(callNode, 'out_return_1', outputNode, 'return_1'));

    await area.translate(inputNode.id, { x: -620, y: 100 });
    await area.translate(definitionNode.id, { x: -200, y: 0 });
    await area.translate(callNode.id, { x: 420, y: 100 });
    await area.translate(outputNode.id, { x: 700, y: 100 });

    setTimeout(() => {
        AreaExtensions.zoomAt(area, editor.getNodes());
    }, 1);

    // 工具栏：方便添加节点
    const toolbar = document.createElement('div');
    toolbar.className = 'workflow-toolbar';
    const addToolbarButton = (label: string, factory: () => BaseNode) => {
        const button = document.createElement('button');
        button.className = 'workflow-toolbar-button';
        button.textContent = label;
        button.addEventListener('pointerdown', (e) => e.stopPropagation());
        button.addEventListener('contextmenu', (e) => e.stopPropagation());
        button.addEventListener('click', async () => {
            const node = factory();
            await editor.addNode(node);
            await area.translate(node.id, area.area.pointer);
        });
        toolbar.appendChild(button);
    };
    addToolbarButton('添加输入节点', () => new InputNode(area));
    addToolbarButton('添加返回节点', () => new OutputNode(area));
    addToolbarButton('添加函数定义', () => new FunctionDefinitionNode(area));
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

