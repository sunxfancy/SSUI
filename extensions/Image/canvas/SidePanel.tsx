import React from 'react';
import { Card, Elevation, Button, Icon } from "@blueprintjs/core";
import { ContextMenu, ContextMenuItem } from 'ssui_components';
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
    activeLayer: string;
    onLayerChange: (layerId: string, changes: Partial<Layer>) => void;
    onLayerSelect?: (layerId: string) => void;
    onAddLayer?: () => void;
    onDuplicateLayer?: (layerId: string) => void;
    onDeleteLayer?: (layerId: string) => void;
    onRenameLayer?: (layerId: string) => void;
    onMoveLayer?: (layerId: string, direction: 'up' | 'down') => void;
}

interface SidePanelState {
    contextMenu: {
        x: number;
        y: number;
        layerId: string;
    } | null;
}

export class SidePanel extends React.Component<SidePanelProps, SidePanelState> {
    constructor(props: SidePanelProps) {
        super(props);
        this.state = {
            contextMenu: null
        };
    }

    openLayerContextMenu = (e: React.MouseEvent, layerId: string) => {
        e.preventDefault();
        e.stopPropagation();
        this.props.onLayerSelect?.(layerId);
        this.setState({
            contextMenu: {
                x: e.clientX,
                y: e.clientY,
                layerId
            }
        });
    };

    openEmptyContextMenu = (e: React.MouseEvent) => {
        e.preventDefault();
        this.setState({
            contextMenu: {
                x: e.clientX,
                y: e.clientY,
                layerId: ''
            }
        });
    };

    closeContextMenu = () => {
        this.setState({ contextMenu: null });
    };

    renderLayer = (layer: Layer) => {
        const isActive = layer.id === this.props.activeLayer;
        return (
            <Card
                key={layer.id}
                elevation={Elevation.ONE}
                className={`layer-card ${isActive ? 'layer-card-active' : ''}`}
                onClick={() => this.props.onLayerSelect?.(layer.id)}
                onContextMenu={(e) => this.openLayerContextMenu(e, layer.id)}
            >
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
        const { contextMenu } = this.state;
        const layer = contextMenu
            ? this.props.layers.find(l => l.id === contextMenu.layerId)
            : undefined;
        const items: ContextMenuItem[] = contextMenu
            ? layer
                ? [
                    { label: '重命名图层', icon: 'edit', onClick: () => this.props.onRenameLayer?.(layer.id) },
                    { label: '复制图层', icon: 'duplicate', onClick: () => this.props.onDuplicateLayer?.(layer.id) },
                    { dividerBefore: true },
                    { label: '上移', icon: 'arrow-up', disabled: this.props.layers[0]?.id === layer.id, onClick: () => this.props.onMoveLayer?.(layer.id, 'up') },
                    { label: '下移', icon: 'arrow-down', disabled: this.props.layers[this.props.layers.length - 1]?.id === layer.id, onClick: () => this.props.onMoveLayer?.(layer.id, 'down') },
                    { dividerBefore: true },
                    { label: layer.visible ? '隐藏图层' : '显示图层', icon: layer.visible ? 'eye-off' : 'eye-open', onClick: () => this.props.onLayerChange(layer.id, { visible: !layer.visible }) },
                    { label: layer.locked ? '解锁图层' : '锁定图层', icon: layer.locked ? 'unlock' : 'lock', onClick: () => this.props.onLayerChange(layer.id, { locked: !layer.locked }) },
                    { dividerBefore: true, label: '删除图层', icon: 'trash', intent: 'danger', disabled: this.props.layers.length <= 1, onClick: () => this.props.onDeleteLayer?.(layer.id) }
                ]
                : [
                    { label: '新建图层', icon: 'add', onClick: () => this.props.onAddLayer?.() }
                ]
            : [];

        return (
            <div className="side-panel">
                {this.renderConfigPanel()}
                <div className="panel-header">
                    <h3>图层</h3>
                    <Button minimal icon="plus" onClick={() => this.props.onAddLayer?.()} />
                </div>
                <div className="layers-list" onContextMenu={this.openEmptyContextMenu}>
                    {this.props.layers.map(this.renderLayer)}
                </div>
                {contextMenu && (
                    <ContextMenu
                        x={contextMenu.x}
                        y={contextMenu.y}
                        items={items}
                        onClose={this.closeContextMenu}
                    />
                )}
            </div>
        );
    }
} 
