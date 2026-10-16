import React from 'react';
import { Stage, Layer as KonvaLayer, Rect, Group, Circle, Image, Transformer, Line } from 'react-konva';
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
import { CanvasSettings, paddedBounds, alphaBounds } from './CanvasSize';
const MIN_OBJECT_SIZE = 8;

interface ContextMenuState {
    x: number;
    y: number;
    items: ContextMenuItem[];
}

interface AIDrawingCanvasState {
    canvasSettings: CanvasSettings;
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
    brushColor: string;
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
    private activeStrokeId: string | null = null;
    private activePointerId: number | null = null;

    constructor(props: {path: string}) {
        super(props);
        this.state = {
            canvasSettings: { unbounded: false, width: 512, height: 512, margin: 32 },
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
            brushColor: '#1f2937',
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
        this.loadDocument().then(() => window.parent.postMessage({ type: 'ssui-canvas-ready' }, window.location.origin));
        window.addEventListener('message', this.inputMessage);
        this.updateContainerSize();
        window.addEventListener('resize', this.updateContainerSize);
    }

    componentWillUnmount() {
        window.removeEventListener('message', this.inputMessage);
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

    private readSettings = (value: any): CanvasSettings | undefined => {
        if (!value || typeof value.unbounded !== 'boolean' ||
            !Number.isInteger(value.width) || value.width < 1 ||
            !Number.isInteger(value.height) || value.height < 1 ||
            !Number.isInteger(value.margin) || value.margin < 0) return undefined;
        return value;
    };
    private inputMode = new URLSearchParams(window.location.search).has('input');
    private exportImage = () => {
        const stage = this.stageRef.current.clone();
        try {
            stage.position({ x: 0, y: 0 });
            stage.scale({ x: 1, y: 1 });
            stage.find('.editor-overlay').forEach((node: any) => node.destroy());
            const settings = this.state.canvasSettings;
            let bounds = { ...this.state.targetPosition, width: settings.width, height: settings.height };
            if (settings.unbounded) {
                const rect = stage.getClientRect({ skipTransform: true });
                const x = Math.floor(rect.x), y = Math.floor(rect.y);
                const width = Math.max(1, Math.ceil(rect.x + rect.width) - x);
                const height = Math.max(1, Math.ceil(rect.y + rect.height) - y);
                const raster = stage.toCanvas({ x, y, width, height, pixelRatio: 1 });
                const pixels = raster.getContext('2d')!.getImageData(0, 0, width, height);
                const ink = alphaBounds(pixels.data, width, height);
                bounds = paddedBounds(ink ? { ...ink, x: ink.x + x, y: ink.y + y } : null, settings.margin);
            }
            return { image: stage.toDataURL({ ...bounds, pixelRatio: 1 }), settings, bounds };
        } finally { stage.destroy(); }
    };
    private loadImage = async (source: string, settings?: CanvasSettings) => {
        if (!source.startsWith('data:image/png;base64,')) throw new Error('不支持的画布图片格式');
        const image = await createImageBitmap(await (await fetch(source)).blob());
        this.setState({ layers: [{ id: 'layer1', name: '画布', visible: true, locked: false, opacity: 1,
            objects: [{ id: this.generateId(), type: 'image', x: 0, y: 0, width: image.width, height: image.height, image }] }],
            activeLayer: 'layer1', canvasSettings: settings ?? { unbounded: false, width: image.width, height: image.height, margin: 32 }, targetPosition: { x: 0, y: 0 }, selectedObjectId: null });
    };
    private loadDocument = async () => {
        if (!this.props.path.endsWith('.canvas')) return;
        try {
            const response = await fetch('/file?' + new URLSearchParams({ path: this.props.path }));
            if (!response.ok) throw new Error('无法读取画布文件');
            const text = await response.text();
            if (!text.trim()) return;
            const doc = JSON.parse(text);
            if (doc.version !== 1 || typeof doc.image !== 'string') throw new Error('不支持的画布格式');
            await this.loadImage(doc.image, this.readSettings(doc.settings));
        } catch (error) { window.alert(String(error)); }
    };
    private saveDocument = async () => {
        try {
            const response = await fetch('/files/upload_json', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: this.props.path, content: JSON.stringify({ version: 1, ...this.exportImage() }) }) });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || '保存失败');
            window.alert('画布已保存');
        } catch (error) { window.alert(String(error)); }
    };
    private inputMessage = async (event: MessageEvent) => {
        if (!this.inputMode || event.origin !== window.location.origin || event.source !== window.parent) return;
        try {
            if (event.data?.type === 'ssui-canvas-load') await this.loadImage(event.data.image, this.readSettings(event.data.settings));
            if (event.data?.type === 'ssui-canvas-export') window.parent.postMessage({ type: 'ssui-canvas-result', ...this.exportImage() }, window.location.origin);
        } catch (error) { window.alert(String(error)); }
    };

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

    handleBrushColorChange = (color: string) => {
        this.setState({ brushColor: color });
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

    private getDrawingPoint = (e: any) => {
        const stage = this.stageRef.current;
        const pointer = stage?.getRelativePointerPosition();
        if (!pointer) return null;
        const nativeEvent = e.evt as PointerEvent;
        const pressure = nativeEvent.pointerType === 'pen'
            ? Math.max(0.08, nativeEvent.pressure || 0.5)
            : 1;
        return { x: pointer.x, y: pointer.y, pressure };
    };

    handlePointerDown = (e: any) => {
        if (this.state.selectedTool !== 'brush' && this.state.selectedTool !== 'eraser') return;
        if (e.evt.button !== undefined && e.evt.button !== 0) return;

        const layer = this.state.layers.find(item => item.id === this.state.activeLayer);
        const point = this.getDrawingPoint(e);
        if (!layer || !layer.visible || layer.locked || !point) return;

        e.evt.preventDefault();
        this.activePointerId = (e.evt as PointerEvent).pointerId ?? null;
        this.activeStrokeId = this.generateId();
        const erasing = this.state.selectedTool === 'eraser';
        this.setState(state => produce(state, draft => {
            const activeLayer = draft.layers.find(item => item.id === draft.activeLayer);
            activeLayer?.objects.push({
                id: this.activeStrokeId!,
                type: 'stroke',
                name: erasing ? '橡皮擦笔迹' : '手绘笔迹',
                x: 0,
                y: 0,
                points: [point],
                stroke: this.state.brushColor,
                strokeWidth: erasing ? this.state.eraserSize : this.state.brushSize,
                strokeStyle: erasing ? 'normal' : this.state.brushStyle as 'normal' | 'airbrush' | 'texture',
                feather: erasing ? this.state.eraserFeather : this.state.brushFeather,
                compositeOperation: erasing ? 'destination-out' : 'source-over'
            });
        }));
    };

    handlePointerMove = (e: any) => {
        if (this.state.selectedTool === 'brush' || this.state.selectedTool === 'eraser') {
            const point = this.getDrawingPoint(e);
            if (!point) return;
            const pointerId = (e.evt as PointerEvent).pointerId ?? null;
            this.setState(state => produce(state, draft => {
                draft.brushPosition = { x: point.x, y: point.y };
                if (this.activeStrokeId && (this.activePointerId === null || pointerId === this.activePointerId)) {
                    const layer = draft.layers.find(item => item.id === draft.activeLayer);
                    const stroke = layer?.objects.find(item => item.id === this.activeStrokeId);
                    const previous = stroke?.points?.[stroke.points.length - 1];
                    if (stroke?.points && (!previous || Math.hypot(point.x - previous.x, point.y - previous.y) >= 0.5)) {
                        stroke.points.push(point);
                    }
                }
            }));
        }
    };  

    handlePointerUp = (e: any) => {
        const pointerId = (e.evt as PointerEvent).pointerId ?? null;
        if (this.activePointerId === null || pointerId === this.activePointerId) {
            this.activeStrokeId = null;
            this.activePointerId = null;
        }
    };

    handlePointerLeave = () => {
        this.activeStrokeId = null;
        this.activePointerId = null;
        this.setState({ brushPosition: null });
    };

    private renderStroke = (object: Layer['objects'][number]) => {
        const points = object.points ?? [];
        if (points.length === 0) return null;
        const styleOpacity = object.strokeStyle === 'airbrush' ? 0.22 : 1;
        const dash = object.strokeStyle === 'texture' ? [2, Math.max(2, (object.strokeWidth ?? 1) * 0.35)] : undefined;
        const segments = points.length === 1 ? [[points[0], points[0]]] : points.slice(1).map((point, index) => [points[index], point]);
        return (
            <Group key={object.id} globalCompositeOperation={object.compositeOperation ?? 'source-over'}>
                {segments.map(([from, to], index) => {
                    const pressure = (from.pressure + to.pressure) / 2;
                    return (
                        <Line
                            key={`${object.id}-${index}`}
                            points={[from.x, from.y, to.x, to.y]}
                            stroke={object.stroke ?? '#1f2937'}
                            strokeWidth={Math.max(0.5, (object.strokeWidth ?? 1) * pressure)}
                            opacity={styleOpacity}
                            lineCap="round"
                            lineJoin="round"
                            dash={dash}
                            shadowColor={object.stroke ?? '#1f2937'}
                            shadowBlur={object.feather ?? 0}
                            shadowOpacity={(object.feather ?? 0) > 0 ? 0.35 : 0}
                            listening={false}
                        />
                    );
                })}
            </Group>
        );
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
                    cursor: viewport.isDraggingViewport()
                        ? 'grabbing'
                        : (this.state.selectedTool === 'brush' || this.state.selectedTool === 'eraser')
                            ? 'crosshair'
                            : 'grab',
                    touchAction: 'none'
                }}
            >
                <div style={{ position: 'absolute', bottom: 12, left: 80, zIndex: 10, background: 'white', color: 'black', padding: 8 }}>
                    <label><input type="checkbox" checked={this.state.canvasSettings.unbounded} onChange={e => this.setState({ canvasSettings: { ...this.state.canvasSettings, unbounded: e.target.checked } })} />无边界</label>
                    {(['width', 'height', 'margin'] as const).map(key => <label key={key} style={{ marginLeft: 8 }}>
                        {{ width: '宽', height: '高', margin: 'Margin（每边）' }[key]}
                        <input type="number" aria-label={key} min={key === 'margin' ? 0 : 1} step={1}
                            disabled={key !== 'margin' && this.state.canvasSettings.unbounded}
                            value={this.state.canvasSettings[key]} style={{ width: 80 }} onChange={e => {
                                const value = Number(e.target.value);
                                if (Number.isInteger(value) && value >= (key === 'margin' ? 0 : 1)) this.setState({ canvasSettings: { ...this.state.canvasSettings, [key]: value } });
                            }} />
                    </label>)}
                    {this.state.canvasSettings.unbounded && <span> 内容 + Margin，尺寸向上对齐 64</span>}
                </div>
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
                    onPointerDown={this.handlePointerDown}
                    onPointerMove={this.handlePointerMove}
                    onPointerUp={this.handlePointerUp}
                    onPointerCancel={this.handlePointerUp}
                    onPointerLeave={this.handlePointerLeave}
                    scaleX={viewport.scale}
                    scaleY={viewport.scale}
                    x={worldPos.x}
                    y={worldPos.y}
                >
                    {this.state.layers.map((layer) => (
                        <KonvaLayer key={layer.id} opacity={layer.opacity}>
                            {/* 移动工具下的放置目标矩形（渲染在图片下方，避免遮挡操作） */}
                            {!this.state.canvasSettings.unbounded && layer.id === this.state.activeLayer &&
                                this.state.selectedTool === 'move' &&
                                !this.state.selectedObjectId && (
                                    <Rect
                                        name="editor-overlay"
                                        x={targetPosition.x}
                                        y={targetPosition.y}
                                        width={this.state.canvasSettings.width}
                                        height={this.state.canvasSettings.height}
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
                                    if (object.type === 'stroke') {
                                        return this.renderStroke(object);
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
                                        name="editor-overlay"
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
                    

                    <KonvaLayer name="editor-overlay">
                        {/* 渲染网格 */}
                        {this.state.showGrid && <Grid viewport={viewport} />}
                        
                        {/* 渲染画笔大小指示器 */}
                        {brushPosition && (this.state.selectedTool === 'brush' || this.state.selectedTool === 'eraser') && (
                            <Group>
                                <Circle
                                    x={brushPosition.x}
                                    y={brushPosition.y}
                                    radius={(this.state.selectedTool === 'eraser' ? this.state.eraserSize : brushSize) / 2}
                                    stroke="black"
                                    strokeWidth={1}
                                    fill="rgba(0, 0, 0, 0.1)"
                                />
                            </Group>
                        )}
                    </KonvaLayer>
                </Stage>

                {/* 添加悬浮面板 */}
                {!this.inputMode && <FloatingPanel path={this.props.path} aiDrawingService={this.drawingService}
                onSelectScript={this.handleSelectScript}
                onImageGenerated={this.handleImageGenerated}/>}
                {!this.inputMode && this.props.path.endsWith('.canvas') && <button style={{ position: 'absolute', top: 8, left: '45%' }} onClick={this.saveDocument}>保存画布</button>}

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
                    brushColor={this.state.brushColor}
                    eraserSize={this.state.eraserSize}
                    eraserFeather={this.state.eraserFeather}
                    shapeType={this.state.shapeType}
                    shapeFeather={this.state.shapeFeather}
                    onToggleGrid={this.toggleGrid}
                    onBrushSizeChange={this.handleBrushSizeChange}
                    onBrushStyleChange={this.handleBrushStyleChange}
                    onBrushFeatherChange={this.handleBrushFeatherChange}
                    onBrushColorChange={this.handleBrushColorChange}
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
