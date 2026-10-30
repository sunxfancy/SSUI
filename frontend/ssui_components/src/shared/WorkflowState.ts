import { NodeEditor } from 'rete';
import { AreaPlugin } from 'rete-area-plugin';
import { ReroutePlugin } from 'rete-connection-reroute-plugin';
import { AreaExtra, BaseNode, Connection, FunctionCallNode, FunctionDefinitionNode, InputNode, OperatorNode, OutputNode, ParamSpec, Schemes } from './Nodes';

type NodeState = {
    id: string; label: string; kind: 'input' | 'output' | 'operator' | 'definition' | 'call';
    position: { x: number; y: number }; selected?: boolean;
    ports?: ParamSpec[]; definition?: string; width?: number; height?: number;
    spec?: { callable: string; module: string; params: Record<string, string>; returns: string[] };
};
export type WorkflowState = {
    version: 1;
    nodes: NodeState[];
    connections: { id: string; source: string; target: string; sourceOutput: string; targetInput: string }[];
    transform: { x: number; y: number; k: number };
    pins: { connectionId: string; position: { x: number; y: number } }[];
};

export function captureWorkflow(editor: NodeEditor<Schemes>, area: AreaPlugin<Schemes, AreaExtra>, reroute: ReroutePlugin<Schemes>): WorkflowState {
    return {
        version: 1,
        nodes: editor.getNodes().map(node => {
            const saved: NodeState = {
                id: node.id, label: node.label, kind: 'operator', selected: node.selected ?? false,
                position: { ...(area.nodeViews.get(node.id)?.position ?? { x: 0, y: 0 }) },
            };
            if (node instanceof InputNode) { saved.kind = 'input'; saved.ports = node.getParameters().map(port => ({ ...port })); }
            if (node instanceof OutputNode) { saved.kind = 'output'; saved.ports = node.getReturns().map(port => ({ ...port })); }
            if (node instanceof FunctionDefinitionNode) { saved.kind = 'definition'; saved.width = node.boxWidth; saved.height = node.boxHeight; }
            if (node instanceof FunctionCallNode) { saved.kind = 'call'; saved.definition = node.definition.id; }
            if (node instanceof OperatorNode && node.callable) {
                saved.spec = { callable: node.callable, module: node.module ?? '', params: { ...node.inputTypes }, returns: Object.values(node.outputTypes) };
            }
            return saved;
        }),
        connections: editor.getConnections().map(({ id, source, target, sourceOutput, targetInput }) => ({ id, source, target, sourceOutput: String(sourceOutput), targetInput: String(targetInput) })),
        transform: { ...area.area.transform },
        pins: reroute.pins.getPins().map(pin => ({ connectionId: pin.connectionId, position: { ...pin.position } })),
    };
}

export async function restoreWorkflow(saved: WorkflowState, editor: NodeEditor<Schemes>, area: AreaPlugin<Schemes, AreaExtra>, reroute: ReroutePlugin<Schemes>) {
    if (saved.version !== 1 || !Array.isArray(saved.nodes) || !Array.isArray(saved.connections)) throw new Error('不支持的工作流状态版本');
    const nodes = new Map<string, BaseNode>();
    const add = async (item: NodeState, node: BaseNode) => {
        node.id = item.id;
        node.label = item.label;
        node.selected = item.selected ?? false;
        nodes.set(item.id, node);
        await editor.addNode(node);
        await area.translate(node.id, item.position);
    };
    for (const item of saved.nodes.filter(node => node.kind !== 'call')) {
        let node: BaseNode;
        switch (item.kind) {
            case 'input':
                node = new InputNode(area);
                for (const port of item.ports ?? []) (node as InputNode).addParameter(port);
                break;
            case 'output':
                node = new OutputNode(area);
                for (const port of item.ports ?? []) (node as OutputNode).addReturn(port);
                break;
            case 'definition': {
                const definition = new FunctionDefinitionNode(area, item.label);
                definition.boxWidth = item.width ?? 560;
                definition.boxHeight = item.height ?? 320;
                node = definition;
                break;
            }
            case 'operator': node = new OperatorNode(item.label, undefined, item.spec); break;
            default: throw new Error('未知的工作流节点');
        }
        await add(item, node);
    }
    for (const node of nodes.values()) if (node instanceof FunctionDefinitionNode) node.sync();
    for (const item of saved.nodes.filter(node => node.kind === 'call')) {
        const definition = nodes.get(item.definition ?? '');
        if (!(definition instanceof FunctionDefinitionNode)) throw new Error('工作流函数定义丢失');
        await add(item, new FunctionCallNode(area, definition));
    }
    for (const item of saved.connections) {
        const source = nodes.get(item.source), target = nodes.get(item.target);
        if (!source || !target) throw new Error('工作流连接节点丢失');
        const connection = new Connection(source, item.sourceOutput, target, item.targetInput);
        connection.id = item.id;
        await editor.addConnection(connection);
    }
    for (const pin of saved.pins ?? []) reroute.add(pin.connectionId, pin.position);
    await area.area.zoom(saved.transform.k);
    await area.area.translate(saved.transform.x, saved.transform.y);
}
