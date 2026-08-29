import React from 'react';
import { Button, Icon, NonIdealState, Tag } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { ComponentRegister, registerComponent } from '../ComponentsManager';
import './MeshArtifact.css';

type MeshPayload = { path?: string; format?: string };

class MeshArtifact extends IComponent<{}, { payload?: MeshPayload }> {
    state: { payload?: MeshPayload } = {};

    override onUpdate(payload: MeshPayload) {
        this.setState({ payload });
    }

    override render() {
        const path = this.state.payload?.path;
        if (!path) return <NonIdealState icon="cube" title="等待 3D 模型" description="运行后可在这里打开或下载 GLB 文件。" />;
        const url = '/file?path=' + encodeURIComponent(path);
        return <div className="mesh-artifact">
            <div className="mesh-artifact-mark"><Icon icon="cube" size={34} /></div>
            <div className="mesh-artifact-copy">
                <strong>{path.split(/[\\/]/).pop()}</strong>
                <span>{path}</span>
                <Tag minimal icon="box">{(this.state.payload?.format || 'glb').toUpperCase()}</Tag>
            </div>
            <div className="mesh-artifact-actions">
                <Button icon="document-open" onClick={() => window.open(url, '_blank')}>打开</Button>
                <Button icon="download" intent="primary" onClick={() => {
                    const link = document.createElement('a'); link.href = url; link.download = ''; link.click();
                }}>下载</Button>
            </div>
        </div>;
    }
}

registerComponent({ name: 'MeshArtifact', type: 'ssui.base.Mesh', port: 'output', component: MeshArtifact } as ComponentRegister);

export { MeshArtifact };
