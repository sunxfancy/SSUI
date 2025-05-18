import { Button } from '@blueprintjs/core';
import { ClassicPreset, GetSchemes } from 'rete';
import { ReactArea2D,  } from 'rete-react-plugin';
import {
    ContextMenuExtra,
} from "rete-context-menu-plugin";
import { AreaPlugin } from 'rete-area-plugin';

class Connection<
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
        | ClassicPreset.InputControl<"number">
        | ClassicPreset.InputControl<"text">
    }
> { }

// Input节点组件
export class InputNode extends BaseNode {
    private parameters: ParameterControl[] = [];
    private socketCounter = 0;

    constructor(private area: AreaPlugin<Schemes, AreaExtra>) {
        super('Input');
        this.addOutput('default', new ClassicPreset.Output(new ClassicPreset.Socket('默认输出')));
        this.addControl('button', new ButtonControl('添加参数', () => {
            console.log('按钮被点击');
            const parameter = new ParameterControl('新参数', 'string');
            this.addControl(`parameter${this.parameters.length}`, parameter);
            this.parameters.push(parameter);
            this.area.update('node', this.id);
        }));
    }

    addOutputSocket() {
        const socketId = `output_${this.socketCounter++}`;
        this.addOutput(socketId, new ClassicPreset.Output(new ClassicPreset.Socket('新输出')));
        this.parameters.push(new ParameterControl('新参数', 'string'));
        return socketId;
    }

    getParameters() {
        return this.parameters;
    }
}

// Output节点组件
export class OutputNode extends BaseNode {
    private returnTypes: string[] = [];
    private socketCounter = 0;

    constructor(private area: AreaPlugin<Schemes, AreaExtra>) {
        super('Output');
        this.addInput('default', new ClassicPreset.Input(new ClassicPreset.Socket('默认输入')));
    }

    addInputSocket() {
        const socketId = `input_${this.socketCounter++}`;
        this.addInput(socketId, new ClassicPreset.Input(new ClassicPreset.Socket('新输入')));
        this.returnTypes.push('string');
        return socketId;
    }

    getReturnTypes() {
        return this.returnTypes;
    }
}


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
            onPointerDown={(e) => e.stopPropagation()}
            onDoubleClick={(e) => e.stopPropagation()}
            onClick={props.data.onClick}
        >
            {props.data.label}
        </Button>
    );
}

export class ParameterControl extends ClassicPreset.Control {
    constructor(public label: string, public type: string) {
        super();
        this.label = label;
        this.type = type;
    }
}

export function ParameterControlRender(props: { data: ParameterControl }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', justifyContent: 'center' }}>
            <input style={{ flex: 1 , width: '50px' }} type="text" value={props.data.label} />
            <input style={{ flex: 1 , width: '50px' }} type="text" value={props.data.type} />
        </div>
    );
}
