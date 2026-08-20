import React from 'react';
import { Card, Elevation, Button, Icon, InputGroup } from "@blueprintjs/core";
import './SidePanel.css';
import { Layer } from './types';

interface SidePanelProps {
    layers: Layer[];
    activeLayer: string;
    onLayerChange: (layerId: string, changes: Partial<Layer>) => void;
    onLayerSelect: (layerId: string) => void;
    onLayerAdd: () => void;
    onLayerDelete: (layerId: string) => void;
    onLayerMove: (layerId: string, direction: 'up' | 'down') => void;
    onLayerRename: (layerId: string, name: string) => void;
    onLayerDuplicate: (layerId: string) => void;
}

interface SidePanelState {
    editingLayerId: string | null;
    editingName: string;
}

export class SidePanel extends React.Component<SidePanelProps, SidePanelState> {
    constructor(props: SidePanelProps) {
        super(props);
        this.state = {
            editingLayerId: null,
            editingName: ''
        };
    }

    startRename = (layer: Layer) => {
        this.setState({
            editingLayerId: layer.id,
            editingName: layer.name
        });
    };

    commitRename = () => {
        const { editingLayerId, editingName } = this.state;
        if (editingLayerId !== null) {
            const name = editingName.trim();
            if (name) {
                this.props.onLayerRename(editingLayerId, name);
            }
        }
        this.setState({ editingLayerId: null, editingName: '' });
    };

    renderLayerName = (layer: Layer, isActive: boolean) => {
        if (this.state.editingLayerId === layer.id) {
            return (
                <InputGroup
                    autoFocus
                    small
                    value={this.state.editingName}
                    onChange={(e: any) => this.setState({ editingName: (e.currentTarget as HTMLInputElement).value })}
                    onKeyDown={(e: any) => {
                        if (e.key === 'Enter') {
                            this.commitRename();
                        } else if (e.key === 'Escape') {
                            this.setState({ editingLayerId: null, editingName: '' });
                        }
                    }}
                    onBlur={this.commitRename}
                    onPointerDown={(e: any) => e.stopPropagation()}
                />
            );
        }
        return (
            <div
                className="layer-name"
                title="双击重命名"
                onDoubleClick={() => this.startRename(layer)}
            >
                {layer.name}
                {isActive && <Icon icon="selection" size={12} className="layer-active-icon" />}
            </div>
        );
    };

    renderLayer = (layer: Layer, displayIndex: number) => {
        const { layers } = this.props;
        const isActive = layer.id === this.props.activeLayer;
        const isFirst = displayIndex === 0;      // 列表最上方 = 最顶层
        const isLast = displayIndex === layers.length - 1; // 列表最下方 = 最底层

        return (
            <Card
                key={layer.id}
                elevation={Elevation.ONE}
                className={`layer-card ${isActive ? 'layer-card-active' : ''}`}
                onClick={() => this.props.onLayerSelect(layer.id)}
                interactive
            >
                <div className="layer-header">
                    {this.renderLayerName(layer, isActive)}
                    <div className="layer-controls">
                        <Button
                            minimal
                            small
                            icon={layer.visible ? "eye-open" : "eye-off"}
                            title={layer.visible ? '隐藏图层' : '显示图层'}
                            onClick={(e) => {
                                e.stopPropagation();
                                this.props.onLayerChange(layer.id, { visible: !layer.visible });
                            }}
                        />
                        <Button
                            minimal
                            small
                            icon={layer.locked ? "lock" : "unlock"}
                            title={layer.locked ? '解锁图层' : '锁定图层'}
                            onClick={(e) => {
                                e.stopPropagation();
                                this.props.onLayerChange(layer.id, { locked: !layer.locked });
                            }}
                        />
                    </div>
                </div>
                <div className="layer-opacity">
                    <Icon icon="tint" size={12} title="不透明度" />
                    <input
                        type="range"
                        min="0"
                        max="100"
                        value={Math.round(layer.opacity * 100)}
                        onChange={(e) => this.props.onLayerChange(layer.id, { opacity: parseInt(e.target.value) / 100 })}
                        onPointerDown={(e) => e.stopPropagation()}
                    />
                    <span>{Math.round(layer.opacity * 100)}%</span>
                </div>
                <div className="layer-footer">
                    <Button
                        minimal
                        small
                        icon="arrow-up"
                        title="上移一层"
                        disabled={isFirst}
                        onClick={(e) => {
                            e.stopPropagation();
                            this.props.onLayerMove(layer.id, 'up');
                        }}
                    />
                    <Button
                        minimal
                        small
                        icon="arrow-down"
                        title="下移一层"
                        disabled={isLast}
                        onClick={(e) => {
                            e.stopPropagation();
                            this.props.onLayerMove(layer.id, 'down');
                        }}
                    />
                    <Button
                        minimal
                        small
                        icon="duplicate"
                        title="复制图层"
                        onClick={(e) => {
                            e.stopPropagation();
                            this.props.onLayerDuplicate(layer.id);
                        }}
                    />
                    <Button
                        minimal
                        small
                        icon="trash"
                        title="删除图层"
                        intent="danger"
                        onClick={(e) => {
                            e.stopPropagation();
                            this.props.onLayerDelete(layer.id);
                        }}
                    />
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
        // 数组第一个元素为最底层，倒序渲染使最顶层显示在列表最上方
        const reversedLayers = [...this.props.layers].reverse();
        return (
            <div className="side-panel">
                {this.renderConfigPanel()}
                <div className="panel-header">
                    <h3>图层</h3>
                    <Button
                        minimal
                        icon="plus"
                        title="新建图层"
                        onClick={this.props.onLayerAdd}
                    />
                </div>
                <div className="layers-list">
                    {reversedLayers.length === 0 ? (
                        <div className="layers-empty">暂无图层，点击 + 新建</div>
                    ) : (
                        reversedLayers.map((layer, index) => this.renderLayer(layer, index))
                    )}
                </div>
            </div>
        );
    }
} 
