import React from 'react';
import { Button, Callout, Icon, NonIdealState, Tag } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { ComponentRegister, registerComponent } from '../ComponentsManager';
import './MeshArtifact.css';
import { MeshPreview } from './MeshPreview';

type MeshQuality = { parts: number; quads: number; removed_zero_area_faces: number; regularized_faces: number;
    degenerate_export_triangles: number; boundary_edges: number; boundary_edges_away_from_input: number; nonmanifold_edges: number };
type MeshPayload = { path?: string; format?: string; preview_path?: string; artifacts?: Record<string, string>; quality?: MeshQuality };

class MeshArtifact extends IComponent<{}, { payload?: MeshPayload }> {
    protected persistedFields: 'payload'[] = ['payload'];
    state: { payload?: MeshPayload } = {};

    override onUpdate(payload: MeshPayload) {
        this.setState({ payload });
    }

    override render() {
        const path = this.state.payload?.path;
        if (!path) return <NonIdealState icon="cube" title="等待 3D 模型" description="运行后可在这里打开或下载 GLB 文件。" />;
        const url = '/file?path=' + encodeURIComponent(path);
        const quality = this.state.payload?.quality;
        return <div className="mesh-artifact">
            {this.state.payload?.preview_path && <MeshPreview key={this.state.payload.preview_path} path={this.state.payload.preview_path} />}
            {quality && <div className="mesh-quality">
                <Tag minimal intent={quality.degenerate_export_triangles ? 'danger' : 'success'}>
                    {quality.parts} 个部件 · {quality.quads} 个四边面 · 退化三角面 {quality.degenerate_export_triangles}
                </Tag>
                <span>已移除 {quality.removed_zero_area_faces} 个零面积面，修复 {quality.regularized_faces} 个塌缩面。</span>
                {quality.boundary_edges > 0 && <Callout compact intent="warning" title="开放边界检查">
                    保留 {quality.boundary_edges} 条开放边界，未自动封口。
                    {quality.boundary_edges_away_from_input > 0 && `其中 ${quality.boundary_edges_away_from_input} 条与输入边界距离较大，请查看报告。`}
                </Callout>}
            </div>}
            <div className="mesh-artifact-mark"><Icon icon="cube" size={34} /></div>
            <div className="mesh-artifact-copy">
                <strong>{path.split(/[\\/]/).pop()}</strong>
                <span>{path}</span>
                <Tag minimal icon="box">{(this.state.payload?.format || 'glb').toUpperCase()}</Tag>
            </div>
            <div className="mesh-artifact-actions">
                {Object.entries(this.state.payload?.artifacts || {}).map(([name, file]) =>
                    <a key={name} href={'/file?path=' + encodeURIComponent(file)} download>{name}</a>)}
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
