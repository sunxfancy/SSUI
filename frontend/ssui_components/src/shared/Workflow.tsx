import React from 'react';
import { createRoot } from 'react-dom/client';
import { NodeEditor, ClassicPreset } from 'rete';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { ReactPlugin, Presets as ReactPresets, useRete, RenderEmit, Presets } from 'rete-react-plugin';
import {
    ConnectionPlugin,
    Presets as ConnectionPresets,
} from "rete-connection-plugin";

import { AreaExtra, ButtonControl, ButtonControlRender, InputNode, OutputNode, ParameterControl, ParameterControlRender, Schemes } from './Nodes';

export interface WorkflowProps {
    path: string;
}

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

    connection.addPreset(ConnectionPresets.classic.setup());

    // 注册自定义节点组件
    reactRender.addPreset(ReactPresets.classic.setup({
        customize: {
            control(context) {
                if (context.payload instanceof ButtonControl) {
                    return ButtonControlRender;
                }
                if (context.payload instanceof ParameterControl) {
                    return ParameterControlRender;
                }
                if (context.payload instanceof ClassicPreset.InputControl) {
                    return Presets.classic.Control;
                }
                return null;
            }
        }
    }));
    

    // 配置插件
    editor.use(area);
    area.use(connection);
    area.use(reactRender);
    AreaExtensions.simpleNodesOrder(area);

    // 添加示例节点
    const inputNode = new InputNode(area);
    const outputNode = new OutputNode(area);
    inputNode.addOutputSocket();
    outputNode.addInputSocket();


    await editor.addNode(inputNode);
    await editor.addNode(outputNode);

    console.log("节点已添加");

    await area.translate(inputNode.id, { x: -150, y: 0 });
    await area.translate(outputNode.id, { x: 150, y: 0 });

    setTimeout(() => {
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

