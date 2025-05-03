import React from 'react';
import { Card, Elevation, Button, Icon } from "@blueprintjs/core";
import './SidePanel.css';

interface Layer {
    id: string;
    name: string;
    visible: boolean;
    locked: boolean;
    opacity: number;
}

interface SidePanelProps {
    layers: Layer[];
    onLayerChange: (layerId: string, changes: Partial<Layer>) => void;
}

export class SidePanel extends React.Component<SidePanelProps> {
    renderLayer = (layer: Layer) => {
        return (
            <Card key={layer.id} elevation={Elevation.ONE} className="layer-card">
                <div className="layer-header">
                    <div className="layer-name">{layer.name}</div>
                    <div className="layer-controls">
                        <Button
                            minimal
                            icon={layer.visible ? "eye-open" : "eye-off"}
                            onClick={() => this.props.onLayerChange(layer.id, { visible: !layer.visible })}
                        />
                        <Button
                            minimal
                            icon={layer.locked ? "lock" : "unlock"}
                            onClick={() => this.props.onLayerChange(layer.id, { locked: !layer.locked })}
                        />
                    </div>
                </div>
                <div className="layer-opacity">
                    <input
                        type="range"
                        min="0"
                        max="100"
                        value={layer.opacity * 100}
                        onChange={(e) => this.props.onLayerChange(layer.id, { opacity: parseInt(e.target.value) / 100 })}
                    />
                    <span>{Math.round(layer.opacity * 100)}%</span>
                </div>
            </Card>
        );
    }

    renderConfigPanel = () => {
        return (
            <div className="config-panel">
                <div className="panel-header">
                    <h3>配置</h3>
                </div>
                <Card elevation={Elevation.ONE} className="config-card">
                    <div className="config-item">
                        <label>画布大小</label>
                        <div className="config-controls">
                            <input type="number" placeholder="宽度" />
                            <input type="number" placeholder="高度" />
                        </div>
                    </div>
                    <div className="config-item">
                        <label>背景颜色</label>
                        <input type="color" />
                    </div>
                    <div className="config-item">
                        <label>网格显示</label>
                        <Button minimal icon="grid" />
                    </div>
                </Card>
            </div>
        );
    }

    render() {
        return (
            <div className="side-panel">
                {this.renderConfigPanel()}
                <div className="panel-header">
                    <h3>图层</h3>
                    <Button minimal icon="plus" />
                </div>
                <div className="layers-list">
                    {this.props.layers.map(this.renderLayer)}
                </div>
            </div>
        );
    }
} 