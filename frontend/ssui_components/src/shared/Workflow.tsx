import React from 'react';
import { createRoot } from 'react-dom/client';
import { NodeEditor, ClassicPreset } from 'rete';
import { AreaPlugin, AreaExtensions, BaseAreaPlugin } from 'rete-area-plugin';
import { ReactPlugin, Presets as ReactPresets, useRete, Drag } from 'rete-react-plugin';
import {
    ConnectionPlugin,
    Presets as ConnectionPresets,
} from "rete-connection-plugin";
import { ReroutePlugin } from "rete-connection-reroute-plugin";
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
import { filterPaletteItems, PALETTE_NODE_ITEMS, PaletteNodeKind } from './NodePalette';

export interface WorkflowProps {
    path: string;
}

interface PythonOperator {
    module: string;
    name: string;
    callable: string;
    params: Record<string, string>;
    returns: string[];
    source: string;
}

interface ReroutePinData {
    id: string;
    position: { x: number; y: number };
    selected?: boolean;
}

type WorkflowRenderPreset = {
    render: (
        context: Extract<AreaExtra, { type: 'render' }>,
        plugin: ReactPlugin<Schemes, AreaExtra>
    ) => React.ReactElement | null | undefined;
};

function ReroutePin(props: {
    pin: ReroutePinData;
    contextMenu: (id: string) => void;
    translate: (id: string, dx: number, dy: number) => void;
    pointerdown: (id: string) => void;
    getPointer: () => { x: number; y: number };
}) {
    const drag = Drag.useDrag(
        (dx, dy) => props.translate(props.pin.id, dx, dy),
        props.getPointer
    );
    return (
        <div
            className={'flow-reroute-pin' + (props.pin.selected ? ' selected' : '')}
            data-testid="pin"
            style={{
                position: 'absolute',
                top: props.pin.position.y - 9,
                left: props.pin.position.x - 9,
            }}
            onPointerDown={(e) => {
                e.stopPropagation();
                e.preventDefault();
                drag.start(e);
                props.pointerdown(props.pin.id);
            }}
            onContextMenu={(e) => {
                e.stopPropagation();
                e.preventDefault();
                props.contextMenu(props.pin.id);
            }}
        />
    );
}

const createEditor = (path: string) => async (container: HTMLElement) => {
    console.log("初始化工作流编辑器");

    const editor = new NodeEditor<Schemes>();
    const area = new AreaPlugin<Schemes, AreaExtra>(container);
    const connection = new ConnectionPlugin<Schemes, AreaExtra>();
    const reactRender = new ReactPlugin<Schemes, AreaExtra>({ createRoot });
    const reroute = new ReroutePlugin<Schemes>();

    const addNode = async (node: BaseNode, position = area.area.pointer) => {
        await editor.addNode(node);
        await area.translate(node.id, position);
    };

    const createPaletteNode = (kind: PaletteNodeKind): BaseNode | undefined => {
        if (kind === 'input') return new InputNode(area);
        if (kind === 'output') return new OutputNode(area);
        if (kind === 'operator') return new OperatorNode('算子');
        if (kind === 'definition') return new FunctionDefinitionNode(area);
        const definition = editor.getNodes().find(
            (node): node is FunctionDefinitionNode => node instanceof FunctionDefinitionNode
        );
        if (kind === 'call' && definition) return new FunctionCallNode(area, definition);
        return undefined;
    };

    const createPythonOperator = (spec: PythonOperator) => new OperatorNode(
        spec.name, undefined, {
            callable: spec.callable,
            module: spec.module,
            params: spec.params,
            returns: spec.returns,
        }
    );

    const addPaletteNode = async (kind: PaletteNodeKind, position = area.area.pointer) => {
        const node = createPaletteNode(kind);
        if (!node) return false;
        await addNode(node, position);
        syncDefinitions();
        return true;
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

    const selector = AreaExtensions.selector();
    const accumulating = {
        active: () => shiftDown || keepMultiSelection,
    };

    AreaExtensions.selectableNodes(area, selector, { accumulating });

    connection.addPreset(ConnectionPresets.classic.setup());
    reactRender.addPreset(ReactPresets.contextMenu.setup());
    // 自定义连线拐点（绿圆点）：可拖拽、可选中、右键删除
    const reroutePreset: WorkflowRenderPreset = {
        render(context, plugin) {
            if (context.data.type !== 'reroute-pins') return null;
            const area = plugin.parentScope(BaseAreaPlugin);
            return (
                <React.Fragment>
                    {context.data.data.pins.map((pin) => (
                        <ReroutePin
                            key={pin.id}
                            pin={pin}
                            contextMenu={(id) => void reroute.remove(id)}
                            translate={(id, dx, dy) => void reroute.translate(id, dx, dy)}
                            pointerdown={(id) => {
                                // 单击切换选中状态（用于高亮，不影响拖拽）
                                const pin = reroute.pins.getPin(id);
                                if (pin?.selected) void reroute.unselect(id);
                                else void reroute.select(id);
                            }}
                            getPointer={() => area.area.pointer}
                        />
                    ))}
                </React.Fragment>
            );
        },
    };
    reactRender.addPreset(reroutePreset);

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
    reactRender.use(reroute);
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

    // 可搜索节点抽屉：点击添加，或拖到画布的精确位置。
    const toolbar = document.createElement('aside');
    toolbar.className = 'workflow-palette';
    toolbar.setAttribute('aria-label', '节点库');
    toolbar.addEventListener('pointerdown', (event) => event.stopPropagation());
    toolbar.addEventListener('contextmenu', (event) => event.stopPropagation());

    const heading = document.createElement('div');
    heading.className = 'workflow-palette-heading';
    heading.innerHTML = '<strong>节点库</strong><span>拖入画布</span>';
    toolbar.appendChild(heading);

    const search = document.createElement('input');
    search.className = 'workflow-palette-search';
    search.type = 'search';
    search.placeholder = '搜索节点或用途…';
    search.setAttribute('aria-label', '搜索节点');
    toolbar.appendChild(search);

    const list = document.createElement('div');
    list.className = 'workflow-palette-list';
    toolbar.appendChild(list);

    let pythonOperators: PythonOperator[] = [];
    const renderPalette = () => {
        list.replaceChildren();
        const items = filterPaletteItems(search.value);
        let currentGroup = '';
        for (const item of items) {
            if (item.group !== currentGroup) {
                currentGroup = item.group;
                const group = document.createElement('div');
                group.className = 'workflow-palette-group';
                group.textContent = currentGroup;
                list.appendChild(group);
            }
            const card = document.createElement('button');
            card.type = 'button';
            card.className = `workflow-palette-card kind-${item.kind}`;
            card.draggable = true;
            card.dataset.nodeKind = item.kind;
            card.innerHTML = `<span class="workflow-palette-card-title">${item.label}</span><span class="workflow-palette-card-description">${item.description}</span>`;
            if (item.kind === 'call' && !editor.getNodes().some((node) => node instanceof FunctionDefinitionNode)) {
                card.disabled = true;
                card.title = '请先添加函数定义';
            }
            card.addEventListener('click', () => void addPaletteNode(item.kind).then(renderPalette));
            card.addEventListener('dragstart', (event) => {
                event.dataTransfer?.setData('application/x-ssui-node', item.kind);
                if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
            });
            list.appendChild(card);
        }
        const query = search.value.trim().toLocaleLowerCase();
        const matchingOperators = pythonOperators.filter((operator) =>
            [operator.name, operator.module, operator.source, ...Object.keys(operator.params), ...Object.values(operator.params)]
                .join(' ').toLocaleLowerCase().includes(query)
        );
        if (matchingOperators.length > 0) {
            const group = document.createElement('div');
            group.className = 'workflow-palette-group';
            group.textContent = 'Python 与扩展';
            list.appendChild(group);
            for (const operator of matchingOperators) {
                const card = document.createElement('button');
                card.type = 'button';
                card.className = 'workflow-palette-card kind-python';
                card.draggable = true;
                card.innerHTML = `<span class="workflow-palette-card-title">${operator.name}</span><span class="workflow-palette-card-description">${operator.source} · ${Object.keys(operator.params).length} 入 / ${operator.returns.length} 出</span>`;
                card.addEventListener('click', () => void addNode(createPythonOperator(operator)));
                card.addEventListener('dragstart', (event) => {
                    event.dataTransfer?.setData('application/x-ssui-python-operator', JSON.stringify(operator));
                    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
                });
                list.appendChild(card);
            }
        }
        if (items.length === 0 && matchingOperators.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'workflow-palette-empty';
            empty.textContent = '没有匹配的节点';
            list.appendChild(empty);
        }
    };
    search.addEventListener('input', renderPalette);
    renderPalette();
    fetch(`/api/flow/operators?flow_path=${encodeURIComponent(path)}`)
        .then((response) => response.json())
        .then((result: { operators?: PythonOperator[] }) => {
            pythonOperators = result.operators ?? [];
            renderPalette();
        })
        .catch(() => {
            pythonOperators = [];
            renderPalette();
        });

    const onDragOver = (event: DragEvent) => {
        const transfer = event.dataTransfer;
        if (transfer && Array.from(transfer.types).some((type) => type.startsWith('application/x-ssui-'))) {
            event.preventDefault();
            transfer.dropEffect = 'copy';
            container.classList.add('workflow-drop-active');
        }
    };
    const onDragLeave = (event: DragEvent) => {
        if (!container.contains(event.relatedTarget as Node | null)) container.classList.remove('workflow-drop-active');
    };
    const onDrop = (event: DragEvent) => {
        const kind = event.dataTransfer?.getData('application/x-ssui-node') as PaletteNodeKind;
        const rawOperator = event.dataTransfer?.getData('application/x-ssui-python-operator');
        container.classList.remove('workflow-drop-active');
        if (!rawOperator && !PALETTE_NODE_ITEMS.some((item) => item.kind === kind)) return;
        event.preventDefault();
        const rect = container.getBoundingClientRect();
        const transform = area.area.transform;
        const position = {
            x: (event.clientX - rect.left - transform.x) / transform.k,
            y: (event.clientY - rect.top - transform.y) / transform.k,
        };
        if (rawOperator) {
            try {
                void addNode(createPythonOperator(JSON.parse(rawOperator) as PythonOperator), position);
            } catch {
                return;
            }
        } else {
            void addPaletteNode(kind, position).then(renderPalette);
        }
    };
    container.addEventListener('dragover', onDragOver);
    container.addEventListener('dragleave', onDragLeave);
    container.addEventListener('drop', onDrop);

    const clearButton = document.createElement('button');
    clearButton.className = 'workflow-palette-clear';
    clearButton.textContent = '清空画布';
    clearButton.addEventListener('pointerdown', (e) => e.stopPropagation());
    clearButton.addEventListener('click', () => void editor.clear().then(renderPalette));
    toolbar.appendChild(clearButton);
    container.appendChild(toolbar);

    return {
        destroy: () => {
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('keyup', onKeyUp);
            container.removeEventListener('dragover', onDragOver);
            container.removeEventListener('dragleave', onDragLeave);
            container.removeEventListener('drop', onDrop);
            toolbar.remove();
            area.destroy();
        },
    };
};

export const Workflow: React.FC<WorkflowProps> = ({ path }) => {
    const factory = React.useMemo(() => createEditor(path), [path]);
    const [ref, editor] = useRete(factory)
    return (
        <div className="workflow-ui" style={{ width: '100%', height: '100vh', position: 'relative' }}>
            <div ref={ref} style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} />
        </div>
    );
};

