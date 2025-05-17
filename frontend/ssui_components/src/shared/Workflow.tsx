import React, { useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { NodeEditor, GetSchemes, ClassicPreset } from 'rete';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { ReactArea2D, ReactPlugin, Presets as ReactPresets, useRete } from 'rete-react-plugin';
import {
    ConnectionPlugin,
    Presets as ConnectionPresets,
} from "rete-connection-plugin";
import {
    ContextMenuExtra,
    ContextMenuPlugin,
    Presets as ContextMenuPresets,
} from "rete-context-menu-plugin";

export interface WorkflowProps {
    path: string;
}

type Schemes = GetSchemes<
    ClassicPreset.Node,
    ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>
>;

type AreaExtra = ReactArea2D<any> | ContextMenuExtra;

const createEditor = async (container: HTMLElement) => {
    console.log("初始化工作流编辑器");

    const editor = new NodeEditor<Schemes>();
    const area = new AreaPlugin<Schemes, AreaExtra>(container);
    const connection = new ConnectionPlugin<Schemes, AreaExtra>();
    const reactRender = new ReactPlugin<Schemes, AreaExtra>({ createRoot });

    // 使用 AreaExtensions 来配置插件
    AreaExtensions.selectableNodes(area, AreaExtensions.selector(), {
        accumulating: AreaExtensions.accumulateOnCtrl()
    });

    reactRender.addPreset(ReactPresets.classic.setup());
    connection.addPreset(ConnectionPresets.classic.setup());

    // 配置插件
    editor.use(area);
    area.use(connection);
    area.use(reactRender);
    AreaExtensions.simpleNodesOrder(area);

    // 添加一个示例节点
    const node = new ClassicPreset.Node('函数输入');
    node.addOutput('output', new ClassicPreset.Output(new ClassicPreset.Socket('参数1')));

    const node2 = new ClassicPreset.Node('函数输出');
    node2.addInput('input', new ClassicPreset.Input(new ClassicPreset.Socket('结果1')));
    await editor.addNode(node);
    await editor.addNode(node2);

    console.log("节点已添加");

    await area.translate(node.id, { x: -150, y: 0 });
    await area.translate(node2.id, { x: 150, y: 0 });

    setTimeout(() => {
        // wait until nodes rendered because they dont have predefined width and height
        AreaExtensions.zoomAt(area, editor.getNodes());
    }, 1);

    return {
        destroy: () => area.destroy(),
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

