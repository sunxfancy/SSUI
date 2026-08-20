import React from 'react';
import { Stage, Layer as KonvaLayer, Rect, Group, Circle, Image } from 'react-konva';
import { AIDrawingService, SSUIAIDrawingService } from './AIDrawingService';
import { Viewport } from './Viewport';
import { Grid } from './Grid';
import { WorldPosition } from './WorldPosition';
import { FloatingPanel } from './FloatingPanel';
import { SidePanel } from './SidePanel';
import Toolbar from './Toolbar';
import { produce } from 'immer';
import { Layer } from './types';

const GRID_SIZE = 64;
const TARGET_SIZE = 512;

interface AIDrawingCanvasState {
    targetPosition: {
        x: number;
        y: number;
    };
    isDragging: boolean;
    layers: Layer[];
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

    handleLayerSelect = (layerId: string) => {
        this.setState({ activeLayer: layerId });
    };

    handleLayerAdd = () => {
        this.setState(prevState => {
            const newLayer: Layer = {
                id: `layer-${Date.now()}`,
                name: `图层 ${prevState.layers.length + 1}`,
                visible: true,
                locked: false,
                opacity: 1,
                objects: []
            };
            return {
                layers: [...prevState.layers, newLayer],
                activeLayer: newLayer.id
            };
        });
    };

    handleLayerDelete = (layerId: string) => {
        this.setState(prevState => {
            const index = prevState.layers.findIndex(layer => layer.id === layerId);
            if (index < 0) {
                return prevState;
            }
            const layers = prevState.layers.filter(layer => layer.id !== layerId);
            let activeLayer = prevState.activeLayer;
            if (activeLayer === layerId) {
                // 删除的是当前激活图层时，优先激活其下方图层；删除最底层时激活上方图层
                const nextIndex = Math.min(Math.max(index - 1, 0), layers.length - 1);
                activeLayer = layers.length > 0 ? layers[nextIndex].id : '';
            }
            return { layers, activeLayer };
        });
    };

    handleLayerMove = (layerId: string, direction: 'up' | 'down') => {
        this.setState(prevState => {
            const index = prevState.layers.findIndex(layer => layer.id === layerId);
            if (index < 0) {
                return prevState;
            }
            // 数组中越靠后层级越高；'up' 表示在面板中上移一层（层级提升）
            const target = direction === 'up' ? index + 1 : index - 1;
            if (target < 0 || target >= prevState.layers.length) {
                return prevState;
            }
            const layers = [...prevState.layers];
            const [layer] = layers.splice(index, 1);
            layers.splice(target, 0, layer);
            return { layers };
        });
    };

    handleLayerRename = (layerId: string, name: string) => {
        this.handleLayerChange(layerId, { name });
    };

    handleLayerDuplicate = (layerId: string) => {
        this.setState(prevState => {
            const index = prevState.layers.findIndex(layer => layer.id === layerId);
            if (index < 0) {
                return prevState;
            }
            const source = prevState.layers[index];
            const duplicate: Layer = {
                ...source,
                id: `layer-${Date.now()}`,
                name: `${source.name} 副本`,
                objects: source.objects.map(obj => ({ ...obj }))
            };
            const layers = [...prevState.layers];
            layers.splice(index + 1, 0, duplicate);
            return {
                layers,
                activeLayer: duplicate.id
            };
        });
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

    handleImageGenerated = async (imageUrl: string) => {
        try {
            console.log('开始加载图片:', imageUrl);
            const img = new window.Image();
            
            // 添加图片加载事件监听
            img.onload = () => console.log('图片加载成功');
            img.onerror = (e) => console.error('图片加载失败:', e);
            
            // 设置跨域属性
            img.crossOrigin = 'anonymous';
            
            img.src = imageUrl;
            
            // 等待图片加载完成
            await new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = reject;
            });
            
            console.log('开始创建 ImageBitmap');
            const image = await createImageBitmap(img);
            console.log('ImageBitmap 创建成功');
            
            this.setState(state => produce(state, draft => {
                const layer = draft.layers.find(layer => layer.id === draft.activeLayer);
                if (layer) {
                    console.log('添加图片', this.state.targetPosition.x, this.state.targetPosition.y);
                    layer.objects.push({
                        type: 'image',
                        x: this.state.targetPosition.x,
                        y: this.state.targetPosition.y,
                        obj: <Image image={image} x={this.state.targetPosition.x} y={this.state.targetPosition.y} />
                    });
                }
            }));
        } catch (error) {
            console.error('图片处理失败:', error);
            // 这里可以添加用户提示
        }
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
                        <KonvaLayer key={layer.id} opacity={layer.opacity}>
                            {layer.visible && (
                                layer.objects.map((object) => {
                                    return object.obj;
                                })
                            )}
                        </KonvaLayer>
                    ))}
                    

                    <KonvaLayer>
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
                    </KonvaLayer>
                </Stage>

                {/* 添加悬浮面板 */}
                <FloatingPanel path={this.props.path} aiDrawingService={this.drawingService} 
                onSelectScript={this.handleSelectScript}
                onImageGenerated={this.handleImageGenerated}/>

                {/* 添加侧边面板 */}
                <SidePanel 
                    layers={layers}
                    activeLayer={this.state.activeLayer}
                    onLayerChange={this.handleLayerChange}
                    onLayerSelect={this.handleLayerSelect}
                    onLayerAdd={this.handleLayerAdd}
                    onLayerDelete={this.handleLayerDelete}
                    onLayerMove={this.handleLayerMove}
                    onLayerRename={this.handleLayerRename}
                    onLayerDuplicate={this.handleLayerDuplicate}
                />
            </div>
        );
    }
}

export default AIDrawingCanvas;
