import React from 'react';
import { Stage, Layer, Rect, Group, Circle } from 'react-konva';
import { AIDrawingService, SSUIAIDrawingService } from './AIDrawingService';
import { Viewport } from './Viewport';
import { Grid } from './Grid';
import { WorldPosition } from './WorldPosition';
import { FloatingPanel } from './FloatingPanel';
import { SidePanel } from './SidePanel';
import Toolbar from './Toolbar';

const GRID_SIZE = 64;
const TARGET_SIZE = 512;

interface DrawableObject {
    type: string;
    x: number;
    y: number;
    obj: React.ReactNode;
}
interface AIDrawingCanvasState {
    targetPosition: {
        x: number;
        y: number;
    };
    isDragging: boolean;
    layers: {
        id: string;
        name: string;
        visible: boolean;
        locked: boolean;
        opacity: number;
        objects: DrawableObject[];
    }[];
    activeLayer: string;
    selectedTool: string;
    brushSize: number;
    brushPosition: {
        x: number;
        y: number;
    } | null;
    worldPosition: WorldPosition;
    viewport: Viewport;
}

class AIDrawingCanvas extends React.Component<{path: string}, AIDrawingCanvasState> {
    private drawingService: AIDrawingService;
    private stageRef: React.RefObject<any>;
    private containerRef: React.RefObject<HTMLDivElement>;

    constructor(props: {path: string}) {
        super(props);
        this.state = {
            targetPosition: { x: 0, y: 0 },
            isDragging: false,
            layers: [
                {
                    id: 'layer1',
                    name: '层1',
                    visible: true,
                    locked: false,
                    opacity: 1,
                    objects: []
                }
            ],
            activeLayer: 'layer1',
            selectedTool: 'move',
            brushSize: 20,
            brushPosition: null,
            worldPosition: new WorldPosition(0, 0),
            viewport: new Viewport(window.innerWidth, window.innerHeight)
        };
        this.drawingService = new SSUIAIDrawingService();
        this.stageRef = React.createRef();
        this.containerRef = React.createRef();
    }

    componentDidMount() {
        this.updateContainerSize();
        window.addEventListener('resize', this.updateContainerSize);
    }

    componentWillUnmount() {
        window.removeEventListener('resize', this.updateContainerSize);
    }

    private updateContainerSize = () => {
        if (this.containerRef.current) {
            const { width, height } = this.containerRef.current.getBoundingClientRect();
            this.setState(prevState => ({
                viewport: prevState.viewport.setSize(width, height)
            }));
        }
    };

    // 对齐到网格
    private snapToGrid = (value: number): number => {
        return Math.round(value / GRID_SIZE) * GRID_SIZE;
    };

    handleDragStart = () => {
        if (this.state.selectedTool != 'move') {
            return;
        }
        this.setState({ isDragging: true });
    };

    handleDragEnd = (e: any) => {
        if (this.state.selectedTool != 'move') {
            return;
        }

        const currentX = e.target.x();
        const currentY = e.target.y();
        
        const newX = this.snapToGrid(currentX);
        const newY = this.snapToGrid(currentY);
        
        this.setState({
            isDragging: false,
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
            this.setState(prevState => ({
                viewport: prevState.viewport.startDragging(pointer)
            }));
        }
    };

    handleViewportDragMove = (e: any) => {
        const stage = this.stageRef.current;
        const pointer = stage.getPointerPosition();
        if (this.state.viewport.isDraggingViewport()) {
            const newViewport = this.state.viewport.handleDrag(pointer);
            this.setState(prevState => ({
                viewport: newViewport,
                worldPosition: prevState.worldPosition.setPosition(
                    -newViewport.position.x / newViewport.scale,
                    -newViewport.position.y / newViewport.scale
                )
            }));
        }
    };

    handleViewportDragEnd = () => {
        this.setState(prevState => ({
            viewport: prevState.viewport.stopDragging()
        }));
    };

    // 处理鼠标滚轮缩放
    handleWheel = (e: any) => {
        e.evt.preventDefault();
        const stage = this.stageRef.current;
        const pointer = stage.getPointerPosition();
        this.setState(prevState => ({
            viewport: prevState.viewport.handleZoom(e.evt.deltaY, pointer)
        }));
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
        this.setState({
            selectedTool: tool
        });
    };

    handleSelectScript = (script: string) => {
        console.log('Selected script:', script);
        // 这里可以添加脚本选择的处理逻辑、

    };

    handlePointerDown = (e: any) => {
    };

    handlePointerMove = (e: any) => {
        if (this.state.selectedTool === 'brush' || this.state.selectedTool === 'eraser') {
            const stage = this.stageRef.current;
            const pointer = stage.getPointerPosition();
            if (pointer) {
                this.setState({
                    brushPosition: {
                        x: pointer.x,
                        y: pointer.y
                    }
                });
            }
        }
    };  

    handlePointerUp = (e: any) => {
        this.setState({ brushPosition: null });
    };

    render() {
        const { targetPosition, isDragging, layers, brushPosition, brushSize } = this.state;
        const viewport = this.state.viewport;
        const worldPos = this.state.worldPosition;
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
                    cursor: viewport.isDraggingViewport() ? 'grabbing' : 'grab'
                }}
                onPointerDown={this.handlePointerDown}
                onPointerMove={this.handlePointerMove}
                onPointerUp={this.handlePointerUp}
            >
                <Toolbar onToolSelect={this.handleToolSelect} />
                <Stage
                    ref={this.stageRef}
                    width={viewport.size.width}
                    height={viewport.size.height}
                    draggable={viewport.isDraggingViewport()}
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
                    {this.state.layers.map((layer) => (
                        <Layer key={layer.id} opacity={layer.opacity}>
                            {layer.visible && (
                                layer.objects.map((object) => {
                                    return object.obj;
                                })
                            )}
                        </Layer>
                    ))}
                    

                    <Layer>
                        {/* 渲染网格 */}
                        <Grid viewport={viewport} />
                        
                        {this.state.selectedTool === 'move' && (
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
                        )}

                        {/* 渲染画笔大小指示器 */}
                        {brushPosition && (this.state.selectedTool === 'brush' || this.state.selectedTool === 'eraser') && (
                            <Group>
                                <Circle
                                    x={brushPosition.x-worldPos.x}
                                    y={brushPosition.y-worldPos.y}
                                    radius={brushSize / 2}
                                    stroke="black"
                                    strokeWidth={1}
                                    fill="rgba(0, 0, 0, 0.1)"
                                />
                            </Group>
                        )}
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
