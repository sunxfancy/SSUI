import React from 'react';
import { Stage, Layer, Rect, Group } from 'react-konva';
import { AIDrawingService, MockAIDrawingService } from './AIDrawingService';
import { Viewport, ViewportState } from './Viewport';
import { Grid } from './Grid';
import { WorldPosition } from './WorldPosition';
import { FloatingPanel } from './FloatingPanel';
import { SidePanel } from './SidePanel';
import Toolbar from './Toolbar';
import {Message} from 'ssui_components';

const BLOCK_SIZE = 512;
const GRID_SIZE = 64;
const TARGET_SIZE = 512;

interface AIDrawingCanvasState {
    targetPosition: {
        x: number;
        y: number;
    };
    isDragging: boolean;
    containerSize: {
        width: number;
        height: number;
    };
    layers: {
        id: string;
        name: string;
        visible: boolean;
        locked: boolean;
        opacity: number;
    }[];
}

class AIDrawingCanvas extends React.Component<{path: string}, AIDrawingCanvasState> {
    private drawingService: AIDrawingService;
    private stageRef: React.RefObject<any>;
    private viewport: Viewport;
    private worldPosition: WorldPosition;
    private containerRef: React.RefObject<HTMLDivElement>;

    constructor(props: {path: string}) {
        super(props);
        this.state = {
            targetPosition: { x: 0, y: 0 },
            isDragging: false,
            containerSize: {
                width: window.innerWidth,
                height: window.innerHeight
            },
            layers: [
                {
                    id: 'layer1',
                    name: '背景层',
                    visible: true,
                    locked: false,
                    opacity: 1
                },
                {
                    id: 'layer2',
                    name: '目标层',
                    visible: true,
                    locked: false,
                    opacity: 1
                }
            ]
        };
        this.drawingService = new MockAIDrawingService();
        this.stageRef = React.createRef();
        this.containerRef = React.createRef();
        this.viewport = new Viewport({
            x: 0,
            y: 0,
            width: window.innerWidth,
            height: window.innerHeight,
            scale: 1
        });
        this.worldPosition = new WorldPosition();
    }

    componentDidMount() {
        this.drawingService.initialize();
        this.updateContainerSize();
        window.addEventListener('resize', this.updateContainerSize);
    }

    componentWillUnmount() {
        window.removeEventListener('resize', this.updateContainerSize);
    }

    private updateContainerSize = () => {
        if (this.containerRef.current) {
            const { width, height } = this.containerRef.current.getBoundingClientRect();
            this.setState({
                containerSize: { width, height }
            });
            this.viewport = new Viewport({
                ...this.viewport.getState(),
                width,
                height
            });
            this.forceUpdate();
        }
    };

    // 对齐到网格
    private snapToGrid = (value: number): number => {
        return Math.round(value / GRID_SIZE) * GRID_SIZE;
    };

    handleDragStart = () => {
        this.setState({ isDragging: true });
    };

    handleDragEnd = (e: any) => {
        this.setState({ isDragging: false });
        
        const currentX = e.target.x();
        const currentY = e.target.y();
        
        const newX = this.snapToGrid(currentX);
        const newY = this.snapToGrid(currentY);
        
        this.setState({
            targetPosition: { x: newX, y: newY }
        });
        
        e.target.x(newX);
        e.target.y(newY);
    };

    // 视口拖动相关处理
    handleViewportDragStart = (e: any) => {
        if (e.evt.button === 1 || e.evt.button === 2) { // 中键或右键
            e.evt.preventDefault();
            const stage = this.stageRef.current;
            const pointer = stage.getPointerPosition();
            this.viewport.startDragging(pointer);
        }
    };

    handleViewportDragMove = (e: any) => {
        const stage = this.stageRef.current;
        const pointer = stage.getPointerPosition();
        if (this.viewport.handleDrag(pointer)) {
            // 更新世界位置
            const viewportState = this.viewport.getState();
            this.worldPosition.setPosition(-viewportState.x, -viewportState.y);
            this.forceUpdate();
        }
    };

    handleViewportDragEnd = () => {
        this.viewport.stopDragging();
    };

    // 处理鼠标滚轮缩放
    handleWheel = (e: any) => {
        e.evt.preventDefault();
        const stage = this.stageRef.current;
        const pointer = stage.getPointerPosition();
        this.viewport.handleZoom(e.evt.deltaY, pointer);
        this.forceUpdate();
    };

    handleLayerChange = (layerId: string, changes: any) => {
        this.setState(prevState => ({
            layers: prevState.layers.map(layer => 
                layer.id === layerId ? { ...layer, ...changes } : layer
            )
        }));
    };

    handleToolSelect = (tool: string) => {
        console.log('Selected tool:', tool);
        // 这里可以添加工具选择的处理逻辑
    };

    handleSelectScript = (script: string) => {
        console.log('Selected script:', script);
        // 这里可以添加脚本选择的处理逻辑
    };

    render() {
        const { targetPosition, isDragging, containerSize, layers } = this.state;
        const viewport = this.viewport.getState();
        const worldPos = this.worldPosition.getPosition();

        return (
            <div 
                ref={this.containerRef}
                style={{ 
                    padding: '0',
                    margin: '0',
                    width: '100vw',
                    height: '100vh',
                    overflow: 'hidden',
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    cursor: this.viewport.isDraggingViewport() ? 'grabbing' : 'grab'
                }}
            >
                <Toolbar onToolSelect={this.handleToolSelect} />
                <Stage
                    ref={this.stageRef}
                    width={containerSize.width}
                    height={containerSize.height}
                    draggable={this.viewport.isDraggingViewport()}
                    onMouseDown={this.handleViewportDragStart}
                    onMouseMove={this.handleViewportDragMove}
                    onMouseUp={this.handleViewportDragEnd}
                    onWheel={this.handleWheel}
                    onContextMenu={(e) => e.evt.preventDefault()}
                    scaleX={viewport.scale}
                    scaleY={viewport.scale}
                    x={worldPos.x}
                    y={worldPos.y}
                >
                    <Layer>
                        {/* 渲染网格 */}
                        <Grid viewport={viewport} />
                        
                        <Rect
                            x={targetPosition.x}
                            y={targetPosition.y}
                            width={TARGET_SIZE}
                            height={TARGET_SIZE}
                            fill={isDragging ? 'rgba(0, 0, 255, 0.2)' : 'rgba(0, 0, 255, 0.1)'}
                            stroke="blue"
                            strokeWidth={2}
                            draggable
                            onDragStart={this.handleDragStart}
                            onDragEnd={this.handleDragEnd}
                        />
                    </Layer>
                </Stage>

                {/* 添加悬浮面板 */}
                <FloatingPanel path={this.props.path} onSelectScript={this.handleSelectScript}/>

                {/* 添加侧边面板 */}
                <SidePanel 
                    layers={layers}
                    onLayerChange={this.handleLayerChange}
                />
            </div>
        );
    }
}

export default AIDrawingCanvas;
