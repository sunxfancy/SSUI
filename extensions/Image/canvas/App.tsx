import React from 'react';
import { Stage, Layer, Rect, Group, Circle, Image } from 'react-konva';
import { AIDrawingService, SSUIAIDrawingService } from './AIDrawingService';
import { Viewport } from './Viewport';
import { Grid } from './Grid';
import { WorldPosition } from './WorldPosition';
import { FloatingPanel } from './FloatingPanel';
import { SidePanel } from './SidePanel';
import Toolbar from './Toolbar';
import { produce } from 'immer';
import { ContextMenu, ContextMenuItem } from 'ssui_components';

const GRID_SIZE = 64;
const TARGET_SIZE = 512;

interface DrawableObject {
    id: string;
    type: string;
    x: number;
    y: number;
    obj: React.ReactNode;
}

interface ContextMenuState {
    x: number;
    y: number;
    items: ContextMenuItem[];
}

interface AIDrawingCanvasState {
    targetPosition: {
        x: number;
        y: number;
    };
    isDragging: boolean;
    showGrid: boolean;
    contextMenu: ContextMenuState | null;
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
            showGrid: true,
            contextMenu: null,
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

    private generateObjectId = (): string =>
        `obj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    private generateLayerId = (): string =>
        `layer_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

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
        if (e.evt.button === 1) { // 中键拖动视口（右键已用于上下文菜单）
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

    addLayer = () => {
        const layer = {
            id: this.generateLayerId(),
            name: `图层 ${this.state.layers.length + 1}`,
            visible: true,
            locked: false,
            opacity: 1,
            objects: [] as DrawableObject[]
        };
        this.setState(prevState => ({
            layers: [...prevState.layers, layer],
            activeLayer: layer.id
        }));
    };

    duplicateLayer = (layerId: string) => {
        this.setState(prevState => produce(prevState, draft => {
            const index = draft.layers.findIndex(layer => layer.id === layerId);
            if (index === -1) return;
            const source = draft.layers[index];
            const copy = {
                ...source,
                id: this.generateLayerId(),
                name: `${source.name} 副本`,
                objects: source.objects.map(obj => ({
                    ...obj,
                    id: this.generateObjectId()
                }))
            };
            draft.layers.splice(index + 1, 0, copy);
        }));
    };

    deleteLayer = (layerId: string) => {
        this.setState(prevState => produce(prevState, draft => {
            if (draft.layers.length <= 1) return;
            const index = draft.layers.findIndex(layer => layer.id === layerId);
            if (index === -1) return;
            draft.layers.splice(index, 1);
            if (draft.activeLayer === layerId) {
                const next = draft.layers[Math.min(index, draft.layers.length - 1)];
                draft.activeLayer = next.id;
            }
        }));
    };

    renameLayer = (layerId: string) => {
        const layer = this.state.layers.find(layer => layer.id === layerId);
        if (!layer) return;
        const name = window.prompt('图层名称', layer.name);
        if (name && name.trim()) {
            this.handleLayerChange(layerId, { name: name.trim() });
        }
    };

    moveLayer = (layerId: string, direction: 'up' | 'down') => {
        this.setState(prevState => produce(prevState, draft => {
            const index = draft.layers.findIndex(layer => layer.id === layerId);
            const target = direction === 'up' ? index - 1 : index + 1;
            if (index === -1 || target < 0 || target >= draft.layers.length) return;
            const [layer] = draft.layers.splice(index, 1);
            draft.layers.splice(target, 0, layer);
        }));
    };

    toggleGrid = () => {
        this.setState(prevState => ({ showGrid: !prevState.showGrid }));
    };

    zoomViewport = (factor: number) => {
        const newViewport = this.state.viewport.zoomBy(factor);
        this.setState({
            viewport: newViewport,
            worldPosition: this.state.worldPosition.setPosition(
                -newViewport.position.x / newViewport.scale,
                -newViewport.position.y / newViewport.scale
            )
        });
    };

    resetViewport = () => {
        const newViewport = this.state.viewport.resetView();
        this.setState({
            viewport: newViewport,
            worldPosition: this.state.worldPosition.setPosition(0, 0)
        });
    };

    openContextMenu = (x: number, y: number, items: ContextMenuItem[]) => {
        this.setState({ contextMenu: { x, y, items } });
    };

    closeContextMenu = () => {
        this.setState({ contextMenu: null });
    };

    // 画布空白处右键菜单
    handleCanvasContextMenu = (e: any) => {
        e.evt.preventDefault();
        if (this.state.viewport.isDraggingViewport()) {
            return;
        }
        const items: ContextMenuItem[] = [
            { label: '新建图层', icon: 'add', onClick: this.addLayer },
            { label: this.state.showGrid ? '隐藏网格' : '显示网格', icon: 'grid', onClick: this.toggleGrid },
            { dividerBefore: true },
            { label: '放大', icon: 'zoom-in', onClick: () => this.zoomViewport(1.2) },
            { label: '缩小', icon: 'zoom-out', onClick: () => this.zoomViewport(1 / 1.2) },
            { label: '重置视图', icon: 'zoom-to-fit', onClick: this.resetViewport }
        ];
        this.openContextMenu(e.evt.clientX, e.evt.clientY, items);
    };

    // 画布对象右键菜单
    openObjectMenu = (e: any, layerId: string, objectId: string) => {
        e.evt.preventDefault();
        e.cancelBubble = true;
        const items: ContextMenuItem[] = [
            { label: '复制对象', icon: 'duplicate', onClick: () => this.duplicateObject(layerId, objectId) },
            { label: '置于顶层', icon: 'bring-forward', onClick: () => this.moveObject(layerId, objectId, 'front') },
            { label: '置于底层', icon: 'send-backward', onClick: () => this.moveObject(layerId, objectId, 'back') },
            { dividerBefore: true, label: '删除对象', icon: 'trash', intent: 'danger', onClick: () => this.deleteObject(layerId, objectId) }
        ];
        this.openContextMenu(e.evt.clientX, e.evt.clientY, items);
    };

    renderObject = (layerId: string, object: DrawableObject) => {
        const element = object.obj as React.ReactElement;
        return React.cloneElement(element, {
            onContextMenu: (e: any) => this.openObjectMenu(e, layerId, object.id)
        });
    };

    duplicateObject = (layerId: string, objectId: string) => {
        this.setState(prevState => produce(prevState, draft => {
            const layer = draft.layers.find(layer => layer.id === layerId);
            if (!layer) return;
            const index = layer.objects.findIndex(obj => obj.id === objectId);
            if (index === -1) return;
            const source = layer.objects[index];
            const copy = {
                id: this.generateObjectId(),
                type: source.type,
                x: source.x + GRID_SIZE,
                y: source.y + GRID_SIZE,
                obj: React.cloneElement(source.obj as React.ReactElement, {
                    x: source.x + GRID_SIZE,
                    y: source.y + GRID_SIZE
                })
            };
            layer.objects.splice(index + 1, 0, copy);
        }));
    };

    deleteObject = (layerId: string, objectId: string) => {
        this.setState(prevState => produce(prevState, draft => {
            const layer = draft.layers.find(layer => layer.id === layerId);
            if (!layer) return;
            const index = layer.objects.findIndex(obj => obj.id === objectId);
            if (index !== -1) {
                layer.objects.splice(index, 1);
            }
        }));
    };

    moveObject = (layerId: string, objectId: string, position: 'front' | 'back') => {
        this.setState(prevState => produce(prevState, draft => {
            const layer = draft.layers.find(layer => layer.id === layerId);
            if (!layer) return;
            const index = layer.objects.findIndex(obj => obj.id === objectId);
            if (index === -1) return;
            const [obj] = layer.objects.splice(index, 1);
            if (position === 'front') {
                layer.objects.push(obj);
            } else {
                layer.objects.unshift(obj);
            }
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

            const position = this.state.targetPosition;
            
            this.setState(state => produce(state, draft => {
                const layer = draft.layers.find(layer => layer.id === draft.activeLayer);
                if (layer) {
                    console.log('添加图片', position.x, position.y);
                    layer.objects.push({
                        id: this.generateObjectId(),
                        type: 'image',
                        x: position.x,
                        y: position.y,
                        obj: <Image image={image} x={position.x} y={position.y} />
                    });
                }
            }));
        } catch (error) {
            console.error('图片处理失败:', error);
            // 这里可以添加用户提示
        }
    };

    render() {
        const { targetPosition, isDragging, layers, brushPosition, brushSize, contextMenu } = this.state;
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
                    onContextMenu={this.handleCanvasContextMenu}
                    scaleX={viewport.scale}
                    scaleY={viewport.scale}
                    x={worldPos.x}
                    y={worldPos.y}
                >
                    {this.state.layers.map((layer) => (
                        <Layer key={layer.id} opacity={layer.opacity}>
                            {layer.visible && (
                                layer.objects.map((object) => {
                                    return (
                                        <React.Fragment key={object.id}>
                                            {this.renderObject(layer.id, object)}
                                        </React.Fragment>
                                    );
                                })
                            )}
                        </Layer>
                    ))}
                    

                    <Layer>
                        {/* 渲染网格 */}
                        {this.state.showGrid && <Grid viewport={viewport} />}
                        
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
                <FloatingPanel path={this.props.path} aiDrawingService={this.drawingService} 
                onSelectScript={this.handleSelectScript}
                onImageGenerated={this.handleImageGenerated}/>

                {/* 添加侧边面板 */}
                <SidePanel 
                    layers={layers}
                    activeLayer={this.state.activeLayer}
                    onLayerChange={this.handleLayerChange}
                    onLayerSelect={this.handleLayerSelect}
                    onAddLayer={this.addLayer}
                    onDuplicateLayer={this.duplicateLayer}
                    onDeleteLayer={this.deleteLayer}
                    onRenameLayer={this.renameLayer}
                    onMoveLayer={this.moveLayer}
                />

                {/* 右键菜单 */}
                {contextMenu && (
                    <ContextMenu
                        x={contextMenu.x}
                        y={contextMenu.y}
                        items={contextMenu.items}
                        onClose={this.closeContextMenu}
                    />
                )}
            </div>
        );
    }
}

export default AIDrawingCanvas;
