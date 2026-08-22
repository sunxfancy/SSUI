import React from 'react';
import { Stage, Layer as KonvaLayer, Rect, Group, Circle, Image, Transformer } from 'react-konva';
import { AIDrawingService, SSUIAIDrawingService } from './AIDrawingService';
import { Viewport } from './Viewport';
import { Grid } from './Grid';
import { WorldPosition } from './WorldPosition';
import { FloatingPanel } from './FloatingPanel';
import { SidePanel } from './SidePanel';
import Toolbar from './Toolbar';
import { produce } from 'immer';
import { Layer } from './types';
import { ContextMenu, ContextMenuItem } from 'ssui_components';

const GRID_SIZE = 64;
const TARGET_SIZE = 512;
const MIN_OBJECT_SIZE = 8;

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
    selectedObjectId: string | null;
    layers: Layer[];
    activeLayer: string;
    focusTarget: 'canvas' | 'tool';
    selectedTool: string;
    brushSize: number;
    brushStyle: string;
    brushFeather: number;
    eraserSize: number;
    eraserFeather: number;
    shapeType: 'rectangle' | 'ellipse';
    shapeFeather: number;
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
    private transformerRef: React.RefObject<any>;
    private imageNodes: Map<string, any> = new Map();
    private idCounter: number = 0;

    constructor(props: {path: string}) {
        super(props);
        this.state = {
            targetPosition: { x: 0, y: 0 },
            isDragging: false,
            showGrid: true,
            contextMenu: null,
            selectedObjectId: null,
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
            focusTarget: 'canvas',
            selectedTool: 'move',
            brushSize: 20,
            brushStyle: 'normal',
            brushFeather: 0,
            eraserSize: 20,
            eraserFeather: 0,
            shapeType: 'rectangle',
            shapeFeather: 0,
            brushPosition: null,
            worldPosition: new WorldPosition(0, 0),
            viewport: new Viewport(window.innerWidth, window.innerHeight)
        };
        this.drawingService = new SSUIAIDrawingService();
        this.stageRef = React.createRef();
        this.containerRef = React.createRef();
        this.transformerRef = React.createRef();
    }

    componentDidMount() {
        this.updateContainerSize();
        window.addEventListener('resize', this.updateContainerSize);
    }

    componentWillUnmount() {
        window.removeEventListener('resize', this.updateContainerSize);
    }

    componentDidUpdate(prevProps: {path: string}, prevState: AIDrawingCanvasState) {
        // 选中对象、图层或工具变化时，重新绑定 8 控制点缩放框
        const selectionChanged = prevState.selectedObjectId !== this.state.selectedObjectId;
        const layersChanged = prevState.layers !== this.state.layers;
        const toolChanged = prevState.selectedTool !== this.state.selectedTool;
        if (!selectionChanged && !layersChanged && !toolChanged) {
            return;
        }

        const transformer = this.transformerRef.current;
        if (!transformer) {
            return;
        }

        const node = this.state.selectedObjectId
            ? this.imageNodes.get(this.state.selectedObjectId)
            : undefined;
        transformer.nodes(node ? [node] : []);
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

    private generateId = (): string => {
        this.idCounter += 1;
        return `canvas-object-${Date.now()}-${this.idCounter}`;
    };

    // 选中图片对象
    private handleSelectObject = (e: any, objectId: string) => {
        if (this.state.selectedTool !== 'move') {
            return;
        }
        e.cancelBubble = true;
        this.setState({ selectedObjectId: objectId });
    };

    // 图片拖动结束：吸附网格并同步状态
    private handleImageDragEnd = (e: any, objectId: string) => {
        if (this.state.selectedTool !== 'move') {
            return;
        }

        const newX = this.snapToGrid(e.target.x());
        const newY = this.snapToGrid(e.target.y());
        e.target.x(newX);
        e.target.y(newY);

        this.setState(state => produce(state, draft => {
            const layer = draft.layers.find(l => l.objects.some(o => o.id === objectId));
            const obj = layer?.objects.find(o => o.id === objectId);
            if (obj) {
                obj.x = newX;
                obj.y = newY;
            }
        }));
    };

    // 8 控制点缩放结束：将 scale 归一化为宽高并写回状态
    private handleTransformEnd = (e: any, objectId: string) => {
        const node = e.target;
        const newWidth = Math.max(MIN_OBJECT_SIZE, node.width() * node.scaleX());
        const newHeight = Math.max(MIN_OBJECT_SIZE, node.height() * node.scaleY());
        // 归一化缩放，后续拖拽/渲染保持一致
        node.scaleX(1);
        node.scaleY(1);

        this.setState(state => produce(state, draft => {
            const layer = draft.layers.find(l => l.objects.some(o => o.id === objectId));
            const obj = layer?.objects.find(o => o.id === objectId);
            if (obj) {
                obj.x = node.x();
                obj.y = node.y();
                obj.width = newWidth;
                obj.height = newHeight;
            }
        }));
    };

    // 限制最小尺寸，防止缩放过小
    private boundBoxFunc = (oldBox: any, newBox: any) => {
        if (Math.abs(newBox.width) < MIN_OBJECT_SIZE || Math.abs(newBox.height) < MIN_OBJECT_SIZE) {
            return oldBox;
        }
        return newBox;
    };

    private registerImageNode = (objectId: string, node: any) => {
        if (node) {
            this.imageNodes.set(objectId, node);
        } else {
            this.imageNodes.delete(objectId);
        }
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
        } else if (e.evt.button === 0 && e.target === this.stageRef.current) {
            // 左键点击空白处取消选中
            // 焦点切换到画布，侧边属性面板显示画布配置
            this.setState({ selectedObjectId: null, focusTarget: 'canvas' });
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
            { label: '新建图层', icon: 'add', onClick: this.handleLayerAdd },
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

    duplicateObject = (layerId: string, objectId: string) => {
        this.setState(prevState => produce(prevState, draft => {
            const layer = draft.layers.find(layer => layer.id === layerId);
            if (!layer) return;
            const index = layer.objects.findIndex(obj => obj.id === objectId);
            if (index === -1) return;
            const source = layer.objects[index];
            const copy = {
                ...source,
                id: this.generateId(),
                x: source.x + GRID_SIZE,
                y: source.y + GRID_SIZE
            };
            layer.objects.splice(index + 1, 0, copy);
            draft.selectedObjectId = copy.id;
        }));
    };

    deleteObject = (layerId: string, objectId: string) => {
        this.setState(prevState => produce(prevState, draft => {
            const layer = draft.layers.find(layer => layer.id === layerId);
            if (!layer) return;
            const index = layer.objects.findIndex(obj => obj.id === objectId);
            if (index !== -1) {
                layer.objects.splice(index, 1);
                if (draft.selectedObjectId === objectId) {
                    draft.selectedObjectId = null;
                }
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
                return { ...prevState };
            }
            const layers = prevState.layers.filter(layer => layer.id !== layerId);
            let activeLayer = prevState.activeLayer;
            if (activeLayer === layerId) {
                // 删除的是当前激活图层时，优先激活其下方图层；删除最底层时激活上方图层
                const nextIndex = Math.min(Math.max(index - 1, 0), layers.length - 1);
                activeLayer = layers.length > 0 ? layers[nextIndex].id : '';
            }
            return { ...prevState, layers, activeLayer };
        });
    };

    handleLayerMove = (layerId: string, direction: 'up' | 'down') => {
        this.setState(prevState => {
            const index = prevState.layers.findIndex(layer => layer.id === layerId);
            if (index < 0) {
                return { ...prevState };
            }
            // 数组中越靠后层级越高；'up' 表示在面板中上移一层（层级提升）
            const target = direction === 'up' ? index + 1 : index - 1;
            if (target < 0 || target >= prevState.layers.length) {
                return { ...prevState };
            }
            const layers = [...prevState.layers];
            const [layer] = layers.splice(index, 1);
            layers.splice(target, 0, layer);
            return { ...prevState, layers };
        });
    };

    handleLayerRename = (layerId: string, name: string) => {
        this.handleLayerChange(layerId, { name });
    };

    handleLayerDuplicate = (layerId: string) => {
        this.setState(prevState => {
            const index = prevState.layers.findIndex(layer => layer.id === layerId);
            if (index < 0) {
                return { ...prevState };
            }
            const source = prevState.layers[index];
            const duplicate: Layer = {
                ...source,
                id: `layer-${Date.now()}`,
                name: `${source.name} 副本`,
                objects: source.objects.map(obj => ({ ...obj, id: this.generateId() }))
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
            selectedTool: tool,
            focusTarget: 'tool'
        });
    };

    handleBrushSizeChange = (size: number) => {
        this.setState({ brushSize: size });
    };

    handleBrushStyleChange = (style: string) => {
        this.setState({ brushStyle: style });
    };

    handleBrushFeatherChange = (feather: number) => {
        this.setState({ brushFeather: feather });
    };

    handleEraserSizeChange = (size: number) => {
        this.setState({ eraserSize: size });
    };

    handleEraserFeatherChange = (feather: number) => {
        this.setState({ eraserFeather: feather });
    };

    handleShapeTypeChange = (shapeType: string) => {
        this.setState({ shapeType: shapeType as 'rectangle' | 'ellipse' });
    };

    handleShapeFeatherChange = (feather: number) => {
        this.setState({ shapeFeather: feather });
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
                    const id = this.generateId();
                    console.log('添加图片', this.state.targetPosition.x, this.state.targetPosition.y);
                    layer.objects.push({
                        id,
                        type: 'image',
                        name: 'canvas-image',
                        x: this.state.targetPosition.x,
                        y: this.state.targetPosition.y,
                        width: image.width,
                        height: image.height,
                        rotation: 0,
                        image
                    });
                    draft.selectedObjectId = id;
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
                <Toolbar selectedTool={this.state.selectedTool} onToolSelect={this.handleToolSelect} />
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
                        <KonvaLayer key={layer.id} opacity={layer.opacity}>
                            {/* 移动工具下的放置目标矩形（渲染在图片下方，避免遮挡操作） */}
                            {layer.id === this.state.activeLayer &&
                                this.state.selectedTool === 'move' &&
                                !this.state.selectedObjectId && (
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
                                )
                            }

                            {layer.visible && (
                                layer.objects.map((object) => {
                                    if (object.type === 'image' && object.image) {
                                        return (
                                            <Image
                                                key={object.id}
                                                id={object.id}
                                                name={object.name || 'canvas-image'}
                                                image={object.image}
                                                x={object.x}
                                                y={object.y}
                                                width={object.width}
                                                height={object.height}
                                                rotation={object.rotation ?? 0}
                                                draggable={this.state.selectedTool === 'move' && !layer.locked}
                                                onMouseDown={(e) => this.handleSelectObject(e, object.id)}
                                                onTap={(e) => this.handleSelectObject(e, object.id)}
                                                onDragEnd={(e) => this.handleImageDragEnd(e, object.id)}
                                                onTransformEnd={(e) => this.handleTransformEnd(e, object.id)}
                                                onContextMenu={(e) => this.openObjectMenu(e, layer.id, object.id)}
                                                ref={(node) => this.registerImageNode(object.id, node)}
                                            />
                                        );
                                    }
                                    return object.obj;
                                })
                            )}

                            {/* 8 控制点缩放框：四角 + 四边中点，独立调整宽高 */}
                            {this.state.selectedObjectId &&
                                this.state.selectedTool === 'move' &&
                                layer.visible &&
                                !layer.locked &&
                                layer.objects.some(o => o.id === this.state.selectedObjectId) && (
                                    <Transformer
                                        ref={this.transformerRef}
                                        rotateEnabled={false}
                                        flipEnabled={false}
                                        enabledAnchors={[
                                            'top-left',
                                            'top-center',
                                            'top-right',
                                            'middle-left',
                                            'middle-right',
                                            'bottom-left',
                                            'bottom-center',
                                            'bottom-right'
                                        ]}
                                        anchorSize={8 / viewport.scale}
                                        anchorCornerRadius={2 / viewport.scale}
                                        anchorStroke="#3b82f6"
                                        anchorFill="#ffffff"
                                        borderStroke="#3b82f6"
                                        borderStrokeWidth={1.5 / viewport.scale}
                                        boundBoxFunc={this.boundBoxFunc}
                                    />
                                )
                            }
                        </KonvaLayer>
                    ))}
                    

                    <KonvaLayer>
                        {/* 渲染网格 */}
                        {this.state.showGrid && <Grid viewport={viewport} />}
                        
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
                    focusTarget={this.state.focusTarget}
                    selectedTool={this.state.selectedTool}
                    showGrid={this.state.showGrid}
                    brushSize={this.state.brushSize}
                    brushStyle={this.state.brushStyle}
                    brushFeather={this.state.brushFeather}
                    eraserSize={this.state.eraserSize}
                    eraserFeather={this.state.eraserFeather}
                    shapeType={this.state.shapeType}
                    shapeFeather={this.state.shapeFeather}
                    onToggleGrid={this.toggleGrid}
                    onBrushSizeChange={this.handleBrushSizeChange}
                    onBrushStyleChange={this.handleBrushStyleChange}
                    onBrushFeatherChange={this.handleBrushFeatherChange}
                    onEraserSizeChange={this.handleEraserSizeChange}
                    onEraserFeatherChange={this.handleEraserFeatherChange}
                    onShapeTypeChange={this.handleShapeTypeChange}
                    onShapeFeatherChange={this.handleShapeFeatherChange}
                    onLayerChange={this.handleLayerChange}
                    onLayerSelect={this.handleLayerSelect}
                    onLayerAdd={this.handleLayerAdd}
                    onLayerDelete={this.handleLayerDelete}
                    onLayerMove={this.handleLayerMove}
                    onLayerRename={this.handleLayerRename}
                    onLayerDuplicate={this.handleLayerDuplicate}
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
