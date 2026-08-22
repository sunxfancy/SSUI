import type * as React from 'react';
import { Button } from '@blueprintjs/core';
import { ClassicPreset, GetSchemes, NodeEditor } from 'rete';
import { Presets as ReactPresets, ReactArea2D, type RenderEmit } from 'rete-react-plugin';
import {
    ContextMenuExtra,
} from "rete-context-menu-plugin";
import { AreaPlugin } from 'rete-area-plugin';

export class Connection<
    A extends BaseNode,
    B extends BaseNode
> extends ClassicPreset.Connection<A, B> { }

export type Schemes = GetSchemes<
    BaseNode,
    Connection<BaseNode, BaseNode>
>;

export type AreaExtra = ReactArea2D<any> | ContextMenuExtra;

export class BaseNode extends ClassicPreset.Node<
    { [key in string]: ClassicPreset.Socket },
    { [key in string]: ClassicPreset.Socket },
    { [key in string]:
        ClassicPreset.Control
        | ButtonControl
        | NameControl
        | InfoControl
        | ClassicPreset.InputControl<"number">
        | ClassicPreset.InputControl<"text">
    }
> {
    protected area?: AreaPlugin<Schemes, AreaExtra>;
    protected refreshOverride?: () => void;

    getEditor(): NodeEditor<Schemes> | undefined {
        if (!this.area) return undefined;
        try {
            return this.area.parentScope(NodeEditor) as NodeEditor<Schemes>;
        } catch {
            return undefined;
        }
    }

    protected refresh(): void {
        if (this.refreshOverride) {
            this.refreshOverride();
        } else if (this.area) {
            void this.area.update('node', this.id);
        }
    }

    protected removeConnectionsForPort(key: string, side: 'input' | 'output'): void {
        const editor = this.getEditor();
        if (!editor) return;
        const doomed = editor.getConnections().filter((c) => {
            if (side === 'output') {
                return c.source === this.id && c.sourceOutput === key;
            }
            return c.target === this.id && c.targetInput === key;
        });
        doomed.forEach((c) => void editor.removeConnection(c.id));
    }

    // 根据“输入参数/返回值”两组规格，同步外层输入/输出端口
    protected syncPortsFromInner(inputSpecs: ParamSpec[], outputSpecs: ParamSpec[]): void {
        const desiredInputs = new Set(inputSpecs.map((p) => `in_${p.key}`));
        const desiredOutputs = new Set(outputSpecs.map((r) => `out_${r.key}`));

        const editor = this.getEditor();
        if (editor) {
            editor.getConnections()
                .filter((c) => {
                    const touchesRemovedInput =
                        c.target === this.id &&
                        c.targetInput in this.inputs &&
                        !desiredInputs.has(c.targetInput as string);
                    const touchesRemovedOutput =
                        c.source === this.id &&
                        c.sourceOutput in this.outputs &&
                        !desiredOutputs.has(c.sourceOutput as string);
                    return touchesRemovedInput || touchesRemovedOutput;
                })
                .forEach((c) => void editor.removeConnection(c.id));
        }

        Object.keys(this.inputs).forEach((key) => {
            if (!desiredInputs.has(key)) this.removeInput(key);
        });
        Object.keys(this.outputs).forEach((key) => {
            if (!desiredOutputs.has(key)) this.removeOutput(key);
        });

        inputSpecs.forEach((p) => {
            const key = `in_${p.key}`;
            if (this.hasInput(key)) {
                this.inputs[key]!.label = p.name;
                this.inputs[key]!.socket = new ClassicPreset.Socket(p.name);
            } else {
                this.addInput(key, new ClassicPreset.Input(new ClassicPreset.Socket(p.name), p.name));
            }
        });

        outputSpecs.forEach((r) => {
            const key = `out_${r.key}`;
            if (this.hasOutput(key)) {
                this.outputs[key]!.label = r.name;
                this.outputs[key]!.socket = new ClassicPreset.Socket(r.name);
            } else {
                this.addOutput(key, new ClassicPreset.Output(new ClassicPreset.Socket(r.name), r.name));
            }
        });
    }
}

export interface ParamSpec {
    key: string;
    name: string;
    type: string;
}

// ============ 控件 ============

export class ButtonControl extends ClassicPreset.Control {
    constructor(public label: string, public onClick: () => void) {
        super();
        this.label = label;
        this.onClick = onClick;
    }
}

export function ButtonControlRender(props: { data: ButtonControl }) {
    return (
        <Button
            small={true}
            minimal={true}
            onPointerDown={(e) => e.stopPropagation()}
            onDoubleClick={(e) => e.stopPropagation()}
            onClick={props.data.onClick}
        >
            {props.data.label}
        </Button>
    );
}

export class NameControl extends ClassicPreset.Control {
    constructor(public value: string, public onChange: (value: string) => void) {
        super();
        this.value = value;
        this.onChange = onChange;
    }
}

export function NameControlRender(props: { data: NameControl }) {
    return (
        <input
            className="flow-name-input"
            type="text"
            value={props.data.value}
            placeholder="名称"
            onPointerDown={(e) => e.stopPropagation()}
            onDoubleClick={(e) => e.stopPropagation()}
            onChange={(e) => props.data.onChange(e.target.value)}
        />
    );
}

export class InfoControl extends ClassicPreset.Control {
    constructor(public text: string) {
        super();
        this.text = text;
    }
}

export function InfoControlRender(props: { data: InfoControl }) {
    return (
        <div
            className="flow-info-text"
            onPointerDown={(e) => e.stopPropagation()}
            onDoubleClick={(e) => e.stopPropagation()}
        >
            {props.data.text}
        </div>
    );
}

// ============ 输入节点（流程参数） ============

export class InputNode extends BaseNode {
    private parameters: ParamSpec[] = [];
    private counter = 0;

    constructor(area?: AreaPlugin<Schemes, AreaExtra>) {
        super('输入');
        this.area = area;
        this.addControl('add', new ButtonControl('添加参数', () => this.addParameter()));
    }

    addParameter(): ParamSpec {
        const key = `param_${this.counter++}`;
        const spec: ParamSpec = {
            key,
            name: `参数 ${this.parameters.length + 1}`,
            type: 'string',
        };
        this.parameters.push(spec);
        this.addOutput(key, new ClassicPreset.Output(new ClassicPreset.Socket(spec.name), spec.name));
        this.refresh();
        return spec;
    }

    removeParameter(key: string): void {
        const index = this.parameters.findIndex((p) => p.key === key);
        if (index < 0) return;
        this.parameters.splice(index, 1);
        this.removeConnectionsForPort(key, 'output');
        this.removeOutput(key);
        this.refresh();
    }

    getParamSpec(key: string): ParamSpec {
        return this.parameters.find((p) => p.key === key)!;
    }

    renameParam(key: string, name: string): void {
        const spec = this.getParamSpec(key);
        spec.name = name;
        const output = this.outputs[key];
        if (output) {
            output.label = name;
            output.socket = new ClassicPreset.Socket(name);
        }
        this.refresh();
    }

    retypeParam(key: string, type: string): void {
        this.getParamSpec(key).type = type;
        this.refresh();
    }

    getParameters(): ParamSpec[] {
        return this.parameters;
    }
}

// ============ 返回节点（返回值） ============

export class OutputNode extends BaseNode {
    private returns: ParamSpec[] = [];
    private counter = 0;

    constructor(area?: AreaPlugin<Schemes, AreaExtra>) {
        super('返回');
        this.area = area;
        this.addControl('add', new ButtonControl('添加返回值', () => this.addReturn()));
    }

    addReturn(): ParamSpec {
        const key = `return_${this.counter++}`;
        const spec: ParamSpec = {
            key,
            name: `返回值 ${this.returns.length + 1}`,
            type: 'string',
        };
        this.returns.push(spec);
        this.addInput(key, new ClassicPreset.Input(new ClassicPreset.Socket(spec.name), spec.name));
        this.refresh();
        return spec;
    }

    removeReturn(key: string): void {
        const index = this.returns.findIndex((r) => r.key === key);
        if (index < 0) return;
        this.returns.splice(index, 1);
        this.removeConnectionsForPort(key, 'input');
        this.removeInput(key);
        this.refresh();
    }

    getReturnSpec(key: string): ParamSpec {
        return this.returns.find((r) => r.key === key)!;
    }

    renameReturn(key: string, name: string): void {
        const spec = this.getReturnSpec(key);
        spec.name = name;
        const input = this.inputs[key];
        if (input) {
            input.label = name;
            input.socket = new ClassicPreset.Socket(name);
        }
        this.refresh();
    }

    retypeReturn(key: string, type: string): void {
        this.getReturnSpec(key).type = type;
        this.refresh();
    }

    getReturns(): ParamSpec[] {
        return this.returns;
    }

    getReturnTypes(): string[] {
        return this.returns.map((r) => r.type);
    }
}

// ============ 输入/返回节点的自定义渲染（参数名直接写在端口旁） ============

const stopPointer = (e: React.PointerEvent) => {
    e.stopPropagation();
};

export function InputNodeRender(props: {
    data: BaseNode;
    emit: RenderEmit<Schemes>;
}): React.JSX.Element {
    const node = props.data as InputNode;
    const outputs = Object.entries(node.outputs).filter(([, output]) => output);
    const addControl = node.controls['add'];

    return (
        <div className={`flow-io-node${node.selected ? ' selected' : ''}`}>
            <div className="flow-io-title">输入</div>
            <div className="flow-io-rows">
                {outputs.map(([key, output]) => {
                    const spec = node.getParamSpec(key);
                    return (
                        <div className="flow-io-row" key={key}>
                            <ReactPresets.classic.RefSocket
                                name="output-socket"
                                side="output"
                                socketKey={key}
                                nodeId={node.id}
                                emit={props.emit}
                                payload={output!.socket}
                            />
                            <input
                                className="flow-io-name"
                                type="text"
                                value={spec.name}
                                placeholder="参数名"
                                onPointerDown={stopPointer}
                                onChange={(e) => node.renameParam(key, e.target.value)}
                            />
                            <input
                                className="flow-io-type"
                                type="text"
                                value={spec.type}
                                placeholder="类型"
                                onPointerDown={stopPointer}
                                onChange={(e) => node.retypeParam(key, e.target.value)}
                            />
                            <button
                                className="flow-io-remove"
                                title="删除参数"
                                onPointerDown={stopPointer}
                                onClick={() => node.removeParameter(key)}
                            >
                                ×
                            </button>
                        </div>
                    );
                })}
            </div>
            <div className="flow-io-add">
                {addControl instanceof ButtonControl && <ButtonControlRender data={addControl} />}
            </div>
        </div>
    );
}

export function OutputNodeRender(props: {
    data: BaseNode;
    emit: RenderEmit<Schemes>;
}): React.JSX.Element {
    const node = props.data as OutputNode;
    const inputs = Object.entries(node.inputs).filter(([, input]) => input);
    const addControl = node.controls['add'];

    return (
        <div className={`flow-io-node${node.selected ? ' selected' : ''}`}>
            <div className="flow-io-title">返回</div>
            <div className="flow-io-rows">
                {inputs.map(([key, input]) => {
                    const spec = node.getReturnSpec(key);
                    return (
                        <div className="flow-io-row" key={key}>
                            <ReactPresets.classic.RefSocket
                                name="input-socket"
                                side="input"
                                socketKey={key}
                                nodeId={node.id}
                                emit={props.emit}
                                payload={input!.socket}
                            />
                            <input
                                className="flow-io-name"
                                type="text"
                                value={spec.name}
                                placeholder="返回值名"
                                onPointerDown={stopPointer}
                                onChange={(e) => node.renameReturn(key, e.target.value)}
                            />
                            <input
                                className="flow-io-type"
                                type="text"
                                value={spec.type}
                                placeholder="类型"
                                onPointerDown={stopPointer}
                                onChange={(e) => node.retypeReturn(key, e.target.value)}
                            />
                            <button
                                className="flow-io-remove"
                                title="删除返回值"
                                onPointerDown={stopPointer}
                                onClick={() => node.removeReturn(key)}
                            >
                                ×
                            </button>
                        </div>
                    );
                })}
            </div>
            <div className="flow-io-add">
                {addControl instanceof ButtonControl && <ButtonControlRender data={addControl} />}
            </div>
        </div>
    );
}

// ============ 算子（函数内部子元素示例） ============

export class OperatorNode extends BaseNode {
    constructor(name: string, refresh?: () => void) {
        super(name);
        this.addInput('input', new ClassicPreset.Input(new ClassicPreset.Socket('输入'), '输入'));
        this.addOutput('output', new ClassicPreset.Output(new ClassicPreset.Socket('输出'), '输出'));
        const nameControl = new NameControl(name, () => {});
        this.addControl(
            'name',
            nameControl
        );
        nameControl.onChange = (value) => {
            this.label = value;
            nameControl.value = value;
            refresh?.();
        };
    }
}

// ============ 函数定义节点（透明大矩形框，框住画布上的一部分节点） ============

export class FunctionDefinitionNode extends BaseNode {
    static counter = 0;
    boxWidth = 560;
    boxHeight = 320;
    inputNode?: InputNode;
    outputNode?: OutputNode;
    hasTooManyInputs = false;
    hasTooManyOutputs = false;
    private callers: FunctionCallNode[] = [];
    private lastSignature = '';

    constructor(
        area: AreaPlugin<Schemes, AreaExtra>,
        name?: string
    ) {
        const fnName = name ?? `函数 ${++FunctionDefinitionNode.counter}`;
        super(fnName);
        this.area = area;

        const nameControl = new NameControl(fnName, () => {});
        this.addControl('name', nameControl);
        nameControl.onChange = (value) => {
            this.label = value;
            nameControl.value = value;
            this.syncCallers();
            this.refresh();
        };
        this.addControl('createCall', new ButtonControl('创建函数调用', () => this.createCall()));
    }

    getArea(): AreaPlugin<Schemes, AreaExtra> | undefined {
        return this.area;
    }

    // 框内输入/输出节点定义函数的参数与返回值
    getParameters(): ParamSpec[] {
        return this.inputNode?.getParameters() ?? [];
    }

    getReturns(): ParamSpec[] {
        return this.outputNode?.getReturns() ?? [];
    }

    // 判断某个节点（按中心点）是否位于该函数框内
    isNodeInside(node: BaseNode): boolean {
        const area = this.area;
        if (!area) return false;
        const defView = area.nodeViews.get(this.id);
        const nodeView = area.nodeViews.get(node.id);
        if (!defView || !nodeView) return false;
        const w = nodeView.element.offsetWidth || 180;
        const h = nodeView.element.offsetHeight || 120;
        const cx = nodeView.position.x + w / 2;
        const cy = nodeView.position.y + h / 2;
        return (
            cx >= defView.position.x &&
            cx <= defView.position.x + this.boxWidth &&
            cy >= defView.position.y &&
            cy <= defView.position.y + this.boxHeight
        );
    }

    registerCaller(caller: FunctionCallNode): void {
        if (!this.callers.includes(caller)) {
            this.callers.push(caller);
        }
    }

    unregisterCaller(caller: FunctionCallNode): void {
        this.callers = this.callers.filter((c) => c !== caller);
    }

    // 依据节点在画布上的位置计算框内成员：
    // 一个框内只能有一个输入节点和一个输出节点，它们定义函数的输入/输出
    sync(): void {
        const editor = this.getEditor();
        const area = this.area;
        if (!editor || !area) return;
        const view = area.nodeViews.get(this.id);
        if (!view) return;

        const inputNodes: InputNode[] = [];
        const outputNodes: OutputNode[] = [];

        for (const node of editor.getNodes()) {
            if (node === this) continue;
            if (!this.isNodeInside(node)) continue;
            if (node instanceof InputNode) inputNodes.push(node);
            else if (node instanceof OutputNode) outputNodes.push(node);
        }

        this.hasTooManyInputs = inputNodes.length > 1;
        this.hasTooManyOutputs = outputNodes.length > 1;
        const inputNode = inputNodes[0];
        const outputNode = outputNodes[0];

        const params = inputNode?.getParameters() ?? [];
        const returns = outputNode?.getReturns() ?? [];
        const signature =
            `${this.label}|` +
            `${inputNode?.id ?? '-'}|${params.map((p) => `${p.key}:${p.name}:${p.type}`).join(',')}|` +
            `${outputNode?.id ?? '-'}|${returns.map((r) => `${r.key}:${r.name}:${r.type}`).join(',')}|` +
            `${this.boxWidth}x${this.boxHeight}|${this.hasTooManyInputs}|${this.hasTooManyOutputs}`;

        if (signature === this.lastSignature) return;
        this.lastSignature = signature;
        this.inputNode = inputNode;
        this.outputNode = outputNode;
        this.syncCallers();
        void area.update('node', this.id);
    }

    // 按选中节点的最小包围盒调整矩形，把节点框起来
    fitToNodes(nodes: BaseNode[]): void {
        const area = this.area;
        if (!area) return;
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        for (const node of nodes) {
            const view = area.nodeViews.get(node.id);
            if (!view) continue;
            const w = view.element.offsetWidth || 180;
            const h = view.element.offsetHeight || 120;
            minX = Math.min(minX, view.position.x);
            minY = Math.min(minY, view.position.y);
            maxX = Math.max(maxX, view.position.x + w);
            maxY = Math.max(maxY, view.position.y + h);
        }
        if (minX === Infinity) return;
        const padding = 46;
        this.boxWidth = Math.max(240, maxX - minX + padding * 2);
        this.boxHeight = Math.max(140, maxY - minY + padding * 2);
        void area.translate(this.id, { x: minX - padding, y: minY - padding });
    }

    // 根据定义创建调用节点，放到定义右侧
    async createCall(): Promise<FunctionCallNode> {
        const caller = new FunctionCallNode(this.area!, this);
        await this.area!.parentScope(NodeEditor).addNode(caller);
        const pos = this.area!.nodeViews.get(this.id)?.position;
        await this.area!.translate(caller.id, {
            x: (pos?.x ?? 0) + this.boxWidth + 80,
            y: pos?.y ?? 0,
        });
        return caller;
    }

    // 函数名/签名变化后，同步所有引用它的调用节点
    private syncCallers(): void {
        this.callers.forEach((caller) => {
            if (caller.syncSignature()) {
                void this.area?.update('node', caller.id);
            }
        });
    }
}

// ============ 函数调用节点（端口数量由被调用的函数定义决定） ============

export class FunctionCallNode extends BaseNode {
    private lastSignature = '';

    constructor(
        area: AreaPlugin<Schemes, AreaExtra>,
        public definition: FunctionDefinitionNode
    ) {
        super(definition.label);
        this.area = area;
        this.definition = definition;
        this.addControl('info', new InfoControl('函数调用'));
        definition.registerCaller(this);
        this.syncSignature();
    }

    // 从函数定义同步名称和端口：输入端口 = 定义内输入节点的参数，输出端口 = 定义内返回节点的返回值
    syncSignature(): boolean {
        const params = this.definition.getParameters();
        const returns = this.definition.getReturns();
        const signature =
            `${this.definition.label}|` +
            `${params.map((p) => `${p.key}:${p.name}:${p.type}`).join(',')}|` +
            `${returns.map((r) => `${r.key}:${r.name}:${r.type}`).join(',')}`;
        if (signature === this.lastSignature) return false;
        this.lastSignature = signature;
        this.label = this.definition.label;
        this.syncPortsFromInner(params, returns);
        return true;
    }
}

// ============ 函数定义节点的自定义渲染（透明矩形框） ============

export function FunctionDefinitionRender(props: {
    data: BaseNode;
    emit: RenderEmit<Schemes>;
}): React.JSX.Element {
    const node = props.data as FunctionDefinitionNode;
    const nameControl = node.controls['name'];
    const createCallControl = node.controls['createCall'];
    const params = node.getParameters().length;
    const returns = node.getReturns().length;

    const onResizePointerDown = (e: React.PointerEvent) => {
        e.stopPropagation();
        e.preventDefault();
        const area = node.getArea();
        if (!area) return;
        const k = area.area.transform.k || 1;
        const startX = e.clientX;
        const startY = e.clientY;
        const startW = node.boxWidth;
        const startH = node.boxHeight;
        const move = (ev: PointerEvent) => {
            node.boxWidth = Math.max(240, startW + (ev.clientX - startX) / k);
            node.boxHeight = Math.max(140, startH + (ev.clientY - startY) / k);
            node.sync();
            void area.update('node', node.id);
        };
        const up = () => {
            window.removeEventListener('pointermove', move);
            window.removeEventListener('pointerup', up);
        };
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', up);
    };

    return (
        <div
            className={`flow-function-def${node.selected ? ' selected' : ''}`}
            style={{ width: node.boxWidth, height: node.boxHeight }}
        >
            <div className="flow-def-header">
                <span className="flow-function-badge">函数定义</span>
                {nameControl instanceof NameControl && <NameControlRender data={nameControl} />}
                {createCallControl instanceof ButtonControl && <ButtonControlRender data={createCallControl} />}
                <span className="flow-function-meta">{params} 参数 · {returns} 返回值</span>
            </div>
            {node.hasTooManyInputs && (
                <div className="flow-def-warning">⚠ 一个函数内只能有一个输入节点</div>
            )}
            {node.hasTooManyOutputs && (
                <div className="flow-def-warning">⚠ 一个函数内只能有一个返回节点</div>
            )}
            <div className="flow-def-resize" onPointerDown={onResizePointerDown} />
        </div>
    );
}
