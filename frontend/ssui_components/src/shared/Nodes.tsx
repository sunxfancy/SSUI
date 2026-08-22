import type { ReactNode } from 'react';
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
        | ParameterControl
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

export class ParameterControl extends ClassicPreset.Control {
    constructor(
        public spec: ParamSpec,
        public onNameChange: (value: string) => void,
        public onTypeChange: (value: string) => void,
        public onRemove: () => void
    ) {
        super();
        this.spec = spec;
        this.onNameChange = onNameChange;
        this.onTypeChange = onTypeChange;
        this.onRemove = onRemove;
    }
}

export function ParameterControlRender(props: { data: ParameterControl }) {
    const control = props.data;
    return (
        <div
            className="flow-param-row"
            onPointerDown={(e) => e.stopPropagation()}
            onDoubleClick={(e) => e.stopPropagation()}
        >
            <input
                className="flow-param-name"
                type="text"
                value={control.spec.name}
                placeholder="参数名"
                onChange={(e) => control.onNameChange(e.target.value)}
            />
            <input
                className="flow-param-type"
                type="text"
                value={control.spec.type}
                placeholder="类型"
                onChange={(e) => control.onTypeChange(e.target.value)}
            />
            <Button
                small={true}
                minimal={true}
                icon="cross"
                title="删除"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={control.onRemove}
            />
        </div>
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

    constructor(
        area?: AreaPlugin<Schemes, AreaExtra>,
        refreshOverride?: () => void
    ) {
        super('输入');
        this.area = area;
        this.refreshOverride = refreshOverride;
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
        this.addControl(
            key,
            new ParameterControl(
                spec,
                (name) => {
                    spec.name = name;
                    this.syncOutput(key);
                    this.refresh();
                },
                (type) => {
                    spec.type = type;
                    this.refresh();
                },
                () => this.removeParameter(key)
            )
        );
        this.refresh();
        return spec;
    }

    removeParameter(key: string): void {
        const index = this.parameters.findIndex((p) => p.key === key);
        if (index < 0) return;
        this.parameters.splice(index, 1);
        this.removeConnectionsForPort(key, 'output');
        this.removeOutput(key);
        this.removeControl(key);
        this.refresh();
    }

    private syncOutput(key: string): void {
        const spec = this.parameters.find((p) => p.key === key);
        const output = this.outputs[key];
        if (spec && output) {
            output.label = spec.name;
            output.socket = new ClassicPreset.Socket(spec.name);
        }
    }

    getParameters(): ParamSpec[] {
        return this.parameters;
    }
}

// ============ 返回节点（返回值） ============

export class OutputNode extends BaseNode {
    private returns: ParamSpec[] = [];
    private counter = 0;

    constructor(
        area?: AreaPlugin<Schemes, AreaExtra>,
        refreshOverride?: () => void
    ) {
        super('返回');
        this.area = area;
        this.refreshOverride = refreshOverride;
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
        this.addControl(
            key,
            new ParameterControl(
                spec,
                (name) => {
                    spec.name = name;
                    this.syncInput(key);
                    this.refresh();
                },
                (type) => {
                    spec.type = type;
                    this.refresh();
                },
                () => this.removeReturn(key)
            )
        );
        this.refresh();
        return spec;
    }

    removeReturn(key: string): void {
        const index = this.returns.findIndex((r) => r.key === key);
        if (index < 0) return;
        this.returns.splice(index, 1);
        this.removeConnectionsForPort(key, 'input');
        this.removeInput(key);
        this.removeControl(key);
        this.refresh();
    }

    private syncInput(key: string): void {
        const spec = this.returns.find((r) => r.key === key);
        const input = this.inputs[key];
        if (spec && input) {
            input.label = spec.name;
            input.socket = new ClassicPreset.Socket(spec.name);
        }
    }

    getReturns(): ParamSpec[] {
        return this.returns;
    }

    getReturnTypes(): string[] {
        return this.returns.map((r) => r.type);
    }
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

// ============ 函数定义节点（一个大方框 = 一个 Python 函数） ============

export class FunctionDefinitionNode extends BaseNode {
    static counter = 0;
    children: BaseNode[] = [];
    private callers: FunctionCallNode[] = [];

    constructor(
        area: AreaPlugin<Schemes, AreaExtra>,
        name?: string
    ) {
        const fnName = name ?? `函数 ${++FunctionDefinitionNode.counter}`;
        super(fnName);
        this.area = area;

        // 内部的输入/返回节点：它们的参数/返回值就是这个函数的输入/输出
        const refresh = () => {
            this.syncSignature();
            this.refresh();
        };
        const innerInput = new InputNode(undefined, refresh);
        const innerOutput = new OutputNode(undefined, refresh);
        this.children.push(innerInput, innerOutput);

        const nameControl = new NameControl(fnName, () => {});
        this.addControl('name', nameControl);
        nameControl.onChange = (value) => {
            this.label = value;
            nameControl.value = value;
            this.syncCallers();
            this.refresh();
        };
        this.addControl('addChild', new ButtonControl('添加子节点', () => this.addChild()));
        this.addControl('createCall', new ButtonControl('创建函数调用', () => this.createCall()));

        // 默认一个参数、一个返回值
        innerInput.addParameter();
        innerOutput.addReturn();
        this.syncSignature();
    }

    getInnerInput(): InputNode {
        return this.children.find((c): c is InputNode => c instanceof InputNode)!;
    }

    getInnerOutput(): OutputNode {
        return this.children.find((c): c is OutputNode => c instanceof OutputNode)!;
    }

    addParameter(): ParamSpec {
        return this.getInnerInput().addParameter();
    }

    removeParameter(key: string): void {
        this.getInnerInput().removeParameter(key);
    }

    addReturn(): ParamSpec {
        return this.getInnerOutput().addReturn();
    }

    removeReturn(key: string): void {
        this.getInnerOutput().removeReturn(key);
    }

    addChild(): BaseNode {
        const child = new OperatorNode(`算子 ${this.children.length - 1}`, () => this.refresh());
        this.children.push(child);
        this.refresh();
        return child;
    }

    registerCaller(caller: FunctionCallNode): void {
        if (!this.callers.includes(caller)) {
            this.callers.push(caller);
        }
    }

    unregisterCaller(caller: FunctionCallNode): void {
        this.callers = this.callers.filter((c) => c !== caller);
    }

    // 根据定义创建/更新调用节点，并放到定义右侧
    async createCall(): Promise<FunctionCallNode> {
        const caller = new FunctionCallNode(this.area!, this);
        await this.area!.parentScope(NodeEditor).addNode(caller);
        const pos = this.area!.nodeViews.get(this.id)?.position;
        await this.area!.translate(caller.id, {
            x: (pos?.x ?? 0) + 300,
            y: pos?.y ?? 0,
        });
        return caller;
    }

    // 把内部输入节点的参数同步为外层输入端口，内部返回节点同步为外层输出端口
    private syncSignature(): void {
        this.syncPortsFromInner(
            this.getInnerInput().getParameters(),
            this.getInnerOutput().getReturns()
        );
        this.syncCallers();
    }

    // 函数签名/名称变化后，同步所有引用它的调用节点
    private syncCallers(): void {
        this.callers.forEach((caller) => {
            caller.syncSignature();
            if (caller.getEditor()?.getNode(caller.id)) {
                void this.area?.update('node', caller.id);
            }
        });
    }
}

// ============ 函数调用节点（端口数量由被调用的函数定义决定） ============

export class FunctionCallNode extends BaseNode {
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

    // 从函数定义同步名称和端口：输入端口 = 定义的参数，输出端口 = 定义的返回值
    syncSignature(): void {
        this.label = this.definition.label;
        this.syncPortsFromInner(
            this.definition.getInnerInput().getParameters(),
            this.definition.getInnerOutput().getReturns()
        );
    }
}

// ============ 函数定义节点的自定义渲染（大矩形框） ============

function renderControl(control: ClassicPreset.Control): ReactNode | null {
    if (control instanceof ButtonControl) {
        return <ButtonControlRender data={control} />;
    }
    if (control instanceof ParameterControl) {
        return <ParameterControlRender data={control} />;
    }
    if (control instanceof NameControl) {
        return <NameControlRender data={control} />;
    }
    if (control instanceof InfoControl) {
        return <InfoControlRender data={control} />;
    }
    return null;
}

function ChildBlock({ child }: { child: BaseNode }) {
    const entries = Object.entries(child.controls).filter(([, control]) => control);
    const addEntry = entries.find(([key]) => key === 'add');
    const rest = entries.filter(([key]) => key !== 'add');
    const ordered = addEntry ? [...rest, addEntry] : rest;

    return (
        <div className="flow-child-node">
            <div className="flow-child-title">{child.label}</div>
            {ordered.map(([, control]) => (
                <div className="flow-child-control" key={control!.id}>
                    {renderControl(control!)}
                </div>
            ))}
        </div>
    );
}

export function FunctionDefinitionRender(props: {
    data: BaseNode;
    emit: RenderEmit<Schemes>;
}): React.JSX.Element {
    const node = props.data as FunctionDefinitionNode;
    const inputs = Object.entries(node.inputs).filter(([, input]) => input);
    const outputs = Object.entries(node.outputs).filter(([, output]) => output);
    const nameControl = node.controls['name'];
    const addChildControl = node.controls['addChild'];
    const createCallControl = node.controls['createCall'];

    return (
        <div className={`flow-function-node${node.selected ? ' selected' : ''}`}>
            <div className="flow-function-header">
                <span className="flow-function-badge">函数定义</span>
                {nameControl instanceof NameControl && <NameControlRender data={nameControl} />}
                <span className="flow-function-meta">
                    {inputs.length} 参数 · {outputs.length} 返回值
                </span>
            </div>

            <div className="flow-function-children">
                {node.children.map((child) => (
                    <ChildBlock key={child.id} child={child} />
                ))}
            </div>

            <div className="flow-function-footer">
                {addChildControl instanceof ButtonControl && <ButtonControlRender data={addChildControl} />}
                {createCallControl instanceof ButtonControl && <ButtonControlRender data={createCallControl} />}
            </div>

            <div className="flow-function-ports">
                <div className="flow-function-inputs">
                    {inputs.map(([key, input]) => (
                        <div className="flow-port-row" key={key}>
                            <ReactPresets.classic.RefSocket
                                name="input-socket"
                                side="input"
                                socketKey={key}
                                nodeId={node.id}
                                emit={props.emit}
                                payload={input!.socket}
                            />
                            <span className="flow-port-label">{input!.label}</span>
                        </div>
                    ))}
                </div>
                <div className="flow-function-outputs">
                    {outputs.map(([key, output]) => (
                        <div className="flow-port-row" key={key}>
                            <span className="flow-port-label">{output!.label}</span>
                            <ReactPresets.classic.RefSocket
                                name="output-socket"
                                side="output"
                                socketKey={key}
                                nodeId={node.id}
                                emit={props.emit}
                                payload={output!.socket}
                            />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
