import { NodeEditor } from 'rete';
import { AreaPlugin } from 'rete-area-plugin';
import { ReroutePlugin } from 'rete-connection-reroute-plugin';
import { captureWorkflow, restoreWorkflow } from '../src/shared/WorkflowState';
import { AreaExtra, BaseNode, Connection, FunctionCallNode, FunctionDefinitionNode, InputNode, OperatorNode, OutputNode, Schemes } from '../src/shared/Nodes';

function workspace() {
    const editor = new NodeEditor<Schemes>();
    const views = new Map();
    const transform = { x: 10, y: -20, k: 1.5 };
    const area = {
        nodeViews: views,
        parentScope: () => editor,
        update: async () => {},
        translate: async (id: string, position: { x: number; y: number }) => {
            views.set(id, { position: { ...position }, element: { offsetWidth: 180, offsetHeight: 120 } });
        },
        area: {
            transform,
            zoom: async (k: number) => { transform.k = k; },
            translate: async (x: number, y: number) => { transform.x = x; transform.y = y; },
        },
    } as unknown as AreaPlugin<Schemes, AreaExtra>;
    const pins: { connectionId: string; position: { x: number; y: number } }[] = [];
    const reroute = {
        pins: { getPins: () => pins },
        add: (connectionId: string, position: { x: number; y: number }) => pins.push({ connectionId, position }),
    } as unknown as ReroutePlugin<Schemes>;
    const add = async (node: BaseNode, x: number, y: number) => {
        await editor.addNode(node);
        await area.translate(node.id, { x, y });
    };
    return { editor, area, reroute, add };
}

it('round trips an edited graph, function links, sparse ports, pins and viewport', async () => {
    const source = workspace();
    const definition = new FunctionDefinitionNode(source.area, 'my function');
    definition.boxWidth = 1000;
    definition.boxHeight = 400;
    await source.add(definition, 0, 0);
    const input = new InputNode(source.area);
    input.addParameter(); input.addParameter();
    input.removeParameter('param_0');
    input.renameParam('param_1', 'prompt'); input.retypeParam('param_1', 'str');
    await source.add(input, 30, 50);
    const output = new OutputNode(source.area);
    output.addReturn(); output.renameReturn('return_0', 'result');
    await source.add(output, 700, 50);
    const operator = new OperatorNode('Python operator', undefined, { callable: 'example.run', module: 'example', params: { prompt: 'str' }, returns: ['str'] });
    await source.add(operator, 350, 50);
    definition.sync();
    const call = new FunctionCallNode(source.area, definition);
    await source.add(call, 1200, 0);
    const connection = new Connection(input, 'param_1', operator, 'prompt');
    await source.editor.addConnection(connection);
    source.reroute.add(connection.id, { x: 250, y: 200 });
    const saved = JSON.parse(JSON.stringify(captureWorkflow(source.editor, source.area, source.reroute)));
    const target = workspace();
    await restoreWorkflow(saved, target.editor, target.area, target.reroute);
    expect(captureWorkflow(target.editor, target.area, target.reroute)).toEqual(saved);
    const restoredCall = target.editor.getNode(call.id) as FunctionCallNode;
    expect(restoredCall.definition).toBe(target.editor.getNode(definition.id));
    expect(restoredCall.inputs['in_param_1']).toBeDefined();
    const restoredInput = target.editor.getNode(input.id) as InputNode;
    expect(restoredInput.addParameter().key).toBe('param_2');
});

it('restores an intentionally empty canvas without creating the demo graph', async () => {
    const source = workspace(), target = workspace();
    const state = captureWorkflow(source.editor, source.area, source.reroute);
    await restoreWorkflow(state, target.editor, target.area, target.reroute);
    expect(target.editor.getNodes()).toEqual([]);
    expect(target.editor.getConnections()).toEqual([]);
});
