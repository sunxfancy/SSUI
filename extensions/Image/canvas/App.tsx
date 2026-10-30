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
import { ContextMenu, ContextMenuItem, UIStateContext, UIStateScope } from 'ssui_components';
import GpuCanvas from './GpuCanvas';
import { hitStroke, smoothPoints, strokePoint, paintLayers } from './drawing';
import { BRUSHES, BrushStyle } from './brushes';
import { vectorize, strokeSamples, moveNode } from './bezier';

const GRID_SIZE = 64;
import { CanvasSettings, paddedBounds, alphaBounds } from './CanvasSize';
const MIN_OBJECT_SIZE = 8;

interface ContextMenuState {
    x: number;
    y: number;
    items: ContextMenuItem[];
}

interface AIDrawingCanvasState {
    restoring?: boolean;
    restoreError?: string;
    assetError?: string;
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
    brushStyle: BrushStyle;
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
    backend: string;
    backendError: string;
    cacheTiles: number;
    cacheBytes: number;
}

class AIDrawingCanvas extends React.Component<{path: string}, AIDrawingCanvasState> {
    static contextType = UIStateContext;
    declare context: React.ContextType<typeof UIStateContext>;
    private durableFields: (keyof AIDrawingCanvasState)[] = ['canvasSettings', 'brushColor', 'targetPosition', 'showGrid', 'selectedObjectId', 'layers', 'activeLayer', 'focusTarget', 'selectedTool', 'brushSize', 'brushStyle', 'brushFeather', 'eraserSize', 'eraserFeather', 'shapeType', 'shapeFeather'];
    private drawingService: AIDrawingService;
    private stageRef: React.RefObject<any>;
    private containerRef: React.RefObject<HTMLDivElement>;
    private transformerRef: React.RefObject<any>;
    private imageNodes: Map<string, any> = new Map();
    private idCounter: number = 0;
    private restoreGeneration = 0;
    private activeStrokeId: string | null = null;
    private activePointerId: number | null = null;
    private undoLayers: Layer[][] = [];
    private redoLayers: Layer[][] = [];
    private fileInput = React.createRef<HTMLInputElement>();

    constructor(props: {path: string}) {
        super(props);
        this.state = {
            restoring: true,
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
            viewport: new Viewport(window.innerWidth, window.innerHeight),
            backend: '初始化', backendError: '', cacheTiles: 0, cacheBytes: 0
        };
        this.drawingService = new SSUIAIDrawingService();
        this.stageRef = React.createRef();
        this.containerRef = React.createRef();
        this.transformerRef = React.createRef();
    }

    componentDidMount() {
        this.restoreCanvas().then(() => window.parent.postMessage({ type: 'ssui-canvas-ready' }, window.location.origin));
        window.addEventListener('message', this.inputMessage);
        this.updateContainerSize();
        window.addEventListener('resize', this.updateContainerSize);
        window.addEventListener('keydown', this.handleKeyDown);
    }

    componentWillUnmount() {
        this.restoreGeneration++;
        this.saveCanvas();
        window.removeEventListener('message', this.inputMessage);
        window.removeEventListener('resize', this.updateContainerSize);
        window.removeEventListener('keydown', this.handleKeyDown);
    }

    componentDidUpdate(prevProps: {path: string}, prevState: AIDrawingCanvasState) {
        this.saveCanvas();
        if (this.state.selectedObjectId && !this.state.layers.some(l => l.visible && !l.locked && l.opacity>0 && l.objects.some(o => o.id===this.state.selectedObjectId))) {
            this.setState({selectedObjectId:null});
        }
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

    private saveCanvas = () => {
        if (!this.context || this.state.restoring || this.state.restoreError) return;
        const snapshot: Record<string, unknown> = {};
        for (const field of this.durableFields) snapshot[field] = this.state[field];
        snapshot.layers = this.state.layers.map(layer => ({ ...layer,
            objects: layer.objects.map(({ image, obj, ...object }) => object) }));
        snapshot.worldPosition = { x: this.state.worldPosition.x, y: this.state.worldPosition.y };
        snapshot.viewport = { position: this.state.viewport.position, scale: this.state.viewport.scale };
        this.context.store.set('/canvas', snapshot);
    };

    private restoreCanvas = async () => {
        const generation = ++this.restoreGeneration;
        const saved = this.context?.store.values['/canvas'] as AIDrawingCanvasState | undefined;
        if (!saved) {
            await this.loadDocument();
            if (generation !== this.restoreGeneration) return;
            await new Promise<void>(resolve => this.setState({ restoring: false }, () => { this.updateContainerSize(); resolve(); }));
            return;
        }
        try {
            const next: Partial<AIDrawingCanvasState> = {};
            for (const field of this.durableFields) {
                if (field in saved) (next as Record<string, unknown>)[field] = saved[field];
            }
            next.layers = await Promise.all(saved.layers.map(async layer => ({ ...layer,
                objects: await Promise.all(layer.objects.map(async object => {
                    if (!object.imagePath) return object;
                    const response = await fetch('/file?' + new URLSearchParams({ path: object.imagePath }));
                    if (!response.ok) throw new Error('无法读取画布图像');
                    return { ...object, image: await createImageBitmap(await response.blob()) };
                })) })));
            if (generation !== this.restoreGeneration) return;
            next.worldPosition = new WorldPosition(saved.worldPosition.x, saved.worldPosition.y);
            next.viewport = new Viewport(window.innerWidth, window.innerHeight);
            next.viewport.position = saved.viewport.position;
            next.viewport.scale = saved.viewport.scale;
            await new Promise<void>(resolve => this.setState({ ...next, restoring: false } as AIDrawingCanvasState, () => { this.updateContainerSize(); resolve(); }));
        } catch {
            if (generation !== this.restoreGeneration) return;
            this.setState({ restoring: false, restoreError: '画布状态恢复失败，已保留原始数据。请检查项目文件后重新打开。' });
        }
    };

    private readSettings = (value: any): CanvasSettings | undefined => {
        if (!value || typeof value.unbounded !== 'boolean' ||
            !Number.isInteger(value.width) || value.width < 1 ||
            !Number.isInteger(value.height) || value.height < 1 ||
            !Number.isInteger(value.margin) || value.margin < 0) return undefined;
        return value;
    };
    private inputMode = new URLSearchParams(window.location.search).has('input');
    private exportImage = () => {
        const raster = document.createElement('canvas');
        const scratch = document.createElement('canvas');
        const render = (bounds: {x:number;y:number;width:number;height:number}) => {
            raster.width=bounds.width;raster.height=bounds.height;
            paintLayers(raster.getContext('2d')!,scratch,this.state.layers,bounds.width,bounds.height,-bounds.x,-bounds.y,1);
        };
            const settings = this.state.canvasSettings;
            let bounds = { ...this.state.targetPosition, width: settings.width, height: settings.height };
            if (settings.unbounded) {
                const extents: {x:number;y:number}[]=[];
                for(const layer of this.state.layers) if(layer.visible&&layer.opacity>0) for(const object of layer.objects) {
                    if(object.compositeOperation==='destination-out')continue;
                    if(object.type==='image') {
                        for(const x of [0,object.width??object.image?.width??0]) for(const y of [0,object.height??object.image?.height??0])
                            extents.push(strokePoint(object,{x,y,pressure:1}));
                    } else {
                        const radius=(object.strokeWidth??1)*2+(object.feather??0)*4+4;
                        const points=object.curve?object.curve.nodes.flatMap(n=>[{x:n[0],y:n[1],pressure:1},{x:n[2],y:n[3],pressure:1},{x:n[4],y:n[5],pressure:1}]):object.points??[];
                        for(const p of points){const q=strokePoint(object,p);extents.push({x:q.x-radius,y:q.y-radius},{x:q.x+radius,y:q.y+radius});}
                    }
                }
                const limits=extents.reduce((b,p)=>({left:Math.min(b.left,p.x),top:Math.min(b.top,p.y),right:Math.max(b.right,p.x),bottom:Math.max(b.bottom,p.y)}),{left:Infinity,top:Infinity,right:-Infinity,bottom:-Infinity});
                const x=Math.floor(extents.length?limits.left:0),y=Math.floor(extents.length?limits.top:0);
                const width=Math.max(1,Math.ceil(extents.length?limits.right-x:1));
                const height=Math.max(1,Math.ceil(extents.length?limits.bottom-y:1));
                render({x,y,width,height});
                const pixels = raster.getContext('2d')!.getImageData(0, 0, width, height);
                const ink = alphaBounds(pixels.data, width, height);
                bounds = paddedBounds(ink ? { ...ink, x: ink.x + x, y: ink.y + y } : null, settings.margin);
            }
            render(bounds);
            return { image: raster.toDataURL('image/png'), settings, bounds };
    };
    private storeImage = async (blob: Blob): Promise<string | undefined> => {
        if (!this.context) return undefined;
        const body = new FormData();
        body.append('file', blob, 'canvas-image');
        const response = await fetch('/api/ui_state_asset?' + new URLSearchParams({ script_path: this.props.path }), { method: 'POST', body });
        if (!response.ok) throw new Error('无法保存画布图像');
        return (await response.json()).path;
    };
    private loadImage = async (source: string, settings?: CanvasSettings) => {
        if (!source.startsWith('data:image/png;base64,')) throw new Error('不支持的画布图片格式');
        const blob = await (await fetch(source)).blob();
        const imagePath = await this.storeImage(blob);
        const image = await createImageBitmap(blob);
        this.setState({ layers: [{ id: 'layer1', name: '画布', visible: true, locked: false, opacity: 1,
            objects: [{ id: this.generateId(), type: 'image', x: 0, y: 0, width: image.width, height: image.height, image, imagePath }] }],
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

    private checkpoint = () => {
        if (this.undoLayers[this.undoLayers.length-1] !== this.state.layers) {
            this.undoLayers.push(this.state.layers);
            if (this.undoLayers.length>64) this.undoLayers.shift();
        }
        this.redoLayers=[];
    };
    private undo = () => {
        const layers=this.undoLayers.pop();
        if (layers) {this.redoLayers.push(this.state.layers);this.setState({layers,selectedObjectId:null,
            activeLayer:layers.some(l=>l.id===this.state.activeLayer)?this.state.activeLayer:layers[0]?.id ?? ''});}
    };
    private redo = () => {
        const layers=this.redoLayers.pop();
        if (layers) {this.undoLayers.push(this.state.layers);this.setState({layers,selectedObjectId:null,
            activeLayer:layers.some(l=>l.id===this.state.activeLayer)?this.state.activeLayer:layers[0]?.id ?? ''});}
    };
    private handleKeyDown = (e: KeyboardEvent) => {
        if ((e.target as HTMLElement)?.closest('input,textarea,select,[contenteditable="true"]')) return;
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase()==='z') {e.preventDefault();e.shiftKey?this.redo():this.undo();}
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase()==='y') {e.preventDefault();this.redo();}
        if (e.key==='Delete' || e.key==='Backspace') {
            const layer=this.state.layers.find(l=>l.objects.some(o=>o.id===this.state.selectedObjectId));
            if (layer && this.state.selectedObjectId) {e.preventDefault();this.deleteObject(layer.id,this.state.selectedObjectId);}
        }
    };
    private handleBackend = (backend: string, backendError='') => this.setState({backend,backendError});
    private handleCacheStats = (tiles: number, bytes: number) => {
        if (this.state.cacheTiles!==tiles || this.state.cacheBytes!==bytes) this.setState({cacheTiles:tiles,cacheBytes:bytes});
    };
    private editStroke = (change: (o: Layer['objects'][number]) => void) => {
        this.setState(state=>produce(state,draft=>{
            const layer=draft.layers.find(l=>l.visible && !l.locked && l.opacity>0 && l.objects.some(o=>o.id===draft.selectedObjectId));
            const object=layer?.objects.find(o=>o.id===draft.selectedObjectId);
            if (object?.type==='stroke') change(object);
        }));
    };
    private importImage = async (file: File) => {
        const imagePath = await this.storeImage(file);
        const image=await createImageBitmap(file);
        const layer=this.state.layers.find(l=>l.id===this.state.activeLayer && l.visible && !l.locked);
        if (!layer) {image.close();return;}
        this.checkpoint();
        this.setState(state=>produce(state,draft=>{
            const target=draft.layers.find(l=>l.id===layer.id);
            if (!target || target.locked) return;
            const id=this.generateId();
            target.objects.push({id,type:'image',name:file.name,x:120,y:120,width:image.width,height:image.height,image,imagePath});
            draft.selectedObjectId=id;draft.selectedTool='move';
        }));
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
        if (this.state.layers.find(l=>l.objects.some(o=>o.id===objectId))?.locked) return;
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
        } else if (e.evt.button === 0 && e.target === this.stageRef.current && this.state.selectedTool !== 'edit' && this.state.selectedTool !== 'move') {
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
                    newViewport.position.x,
                    newViewport.position.y
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
        this.setState(prevState => {
            const viewport=prevState.viewport.handleZoom(e.evt.deltaY,pointer);
            return {viewport,worldPosition:prevState.worldPosition.setPosition(viewport.position.x,viewport.position.y)};
        });
    };

    toggleGrid = () => {
        this.setState(prevState => ({ showGrid: !prevState.showGrid }));
    };

    zoomViewport = (factor: number) => {
        const newViewport = this.state.viewport.zoomBy(factor);
        this.setState({
            viewport: newViewport,
            worldPosition: this.state.worldPosition.setPosition(
                newViewport.position.x,
                newViewport.position.y
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
        if (this.state.layers.find(l=>l.id===layerId)?.locked) return;
        this.checkpoint();
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
        if (this.state.layers.find(l=>l.id===layerId)?.locked) return;
        this.checkpoint();
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
        if (this.state.layers.find(l=>l.id===layerId)?.locked) return;
        this.checkpoint();
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
        this.checkpoint();
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
        this.checkpoint();
        this.setState(prevState => {
            const newLayer: Layer = {
                id: this.generateId(),
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
        this.checkpoint();
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
        this.checkpoint();
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
        this.checkpoint();
        this.setState(prevState => {
            const index = prevState.layers.findIndex(layer => layer.id === layerId);
            if (index < 0) {
                return { ...prevState };
            }
            const source = prevState.layers[index];
            const duplicate: Layer = {
                ...source,
                id: this.generateId(),
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
        const brush=BRUSHES.find(b=>b.id===style);
        if (brush) this.setState({ brushStyle: brush.id, brushSize: brush.size, brushFeather: 0 });
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
        if (!stage) return null;
        const nativeEvent = e.evt as PointerEvent;
        const bounds=stage.container().getBoundingClientRect();
        const pointer=stage.getAbsoluteTransform().copy().invert().point({x:nativeEvent.clientX-bounds.left,y:nativeEvent.clientY-bounds.top});
        const pressure = nativeEvent.pointerType === 'pen'
            ? Math.max(0.08, nativeEvent.pressure || 0.5)
            : 1;
        return { x: pointer.x, y: pointer.y, pressure };
    };

    handlePointerDown = (e: any) => {
        if ((this.state.selectedTool==='edit' || this.state.selectedTool==='move') && e.evt.button===0) {
            // Control handles and image proxies own their events.
            if (e.target!==this.stageRef.current) return;
            const p=this.getDrawingPoint(e);
            const hit=p ? hitStroke(this.state.layers,p.x,p.y,6/this.state.viewport.scale) : null;
            this.setState({selectedObjectId:hit?.object.id ?? null,activeLayer:hit?.layer.id ?? this.state.activeLayer});
            return;
        }
        if (this.state.selectedTool !== 'brush' && this.state.selectedTool !== 'eraser') return;
        if (this.activePointerId!==null) return;
        if (e.evt.button !== undefined && e.evt.button !== 0) return;

        const layer = this.state.layers.find(item => item.id === this.state.activeLayer);
        const point = this.getDrawingPoint(e);
        if (!layer || !layer.visible || layer.locked || !point) return;
        this.checkpoint();

        e.evt.preventDefault();
        this.activePointerId = (e.evt as PointerEvent).pointerId ?? null;
        const target=e.evt.target as HTMLElement;
        if (this.activePointerId!==null && target.setPointerCapture) target.setPointerCapture(this.activePointerId);
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
                strokeStyle: erasing ? 'normal' : this.state.brushStyle,
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
            const native=e.evt as PointerEvent;
            const coalesced=native.getCoalescedEvents?.() ?? [];
            const samples=(coalesced.length?coalesced:[native]).map(evt=>this.getDrawingPoint({evt})).filter((p):p is NonNullable<typeof p>=>p!==null);
            this.setState(state => produce(state, draft => {
                draft.brushPosition = { x: point.x, y: point.y };
                if (this.activeStrokeId && (this.activePointerId === null || pointerId === this.activePointerId)) {
                    const layer = draft.layers.find(item => item.id === draft.activeLayer);
                    const stroke = layer?.objects.find(item => item.id === this.activeStrokeId);
                    for (const sample of samples) {
                        const previous = stroke?.points?.[stroke.points.length - 1];
                        if (stroke?.points && (!previous || Math.hypot(sample.x - previous.x, sample.y - previous.y) >= 0.5)) stroke.points.push(sample);
                    }
                }
            }));
        }
    };  

    handlePointerUp = (e: any) => {
        const pointerId = (e.evt as PointerEvent).pointerId ?? null;
        if (this.activePointerId === null || pointerId === this.activePointerId) {
            const id=this.activeStrokeId;
            if(id) this.setState(state=>produce(state,draft=>{
                const o=draft.layers.flatMap(l=>l.objects).find(o=>o.id===id);
                if(o?.points?.length)vectorize(o,0.5/Math.max(1,state.viewport.scale*(window.devicePixelRatio || 1)));
            }));
            this.activeStrokeId = null;
            this.activePointerId = null;
        }
    };

    handlePointerLeave = () => {
        if (this.activePointerId!==null) return;
        this.setState({ brushPosition: null });
    };

    private renderStrokeControls = () => {
        if (this.state.selectedTool!=='edit' && this.state.selectedTool!=='move') return null;
        const layer=this.state.layers.find(l=>l.visible && !l.locked && l.objects.some(o=>o.id===this.state.selectedObjectId));
        const o=layer?.objects.find(o=>o.id===this.state.selectedObjectId);
        if(o?.curve) {
            const scale=this.state.viewport.scale,nodes=o.curve.nodes;
            const world=(x:number,y:number)=>strokePoint(o,{x,y,pressure:1});
            const local=(x:number,y:number)=>{const r=-(o.rotation ?? 0)*Math.PI/180,dx=x-o.x,dy=y-o.y;
                return {x:dx*Math.cos(r)-dy*Math.sin(r),y:dx*Math.sin(r)+dy*Math.cos(r)};};
            return <Group>
                <Line points={strokeSamples(o,0.3/scale).flatMap(p=>{const w=world(p.x,p.y);return[w.x,w.y];})}
                    stroke="#0ea5e9" strokeWidth={1/scale} dash={[4/scale,4/scale]} listening={false}/>
                {nodes.map((n,i)=>{
                    const anchor=world(n[0],n[1]);
                    return <Group key={`${o.id}-node-${i}`}>
                        {([2,4] as const).map(axis=>{
                            if((axis===2 && i===0) || (axis===4 && i===nodes.length-1))return null;
                            const h=world(n[axis],n[axis+1]);
                            return <Group key={axis}>
                                <Line points={[anchor.x,anchor.y,h.x,h.y]} stroke="#a855f7" strokeWidth={1/scale} listening={false}/>
                                <Circle name={`bezier-handle-${i}-${axis}`} x={h.x} y={h.y} radius={4/scale}
                                    fill="#c084fc" stroke="#7e22ce" strokeWidth={1/scale} draggable
                                    onPointerDown={e=>{e.cancelBubble=true;}} onDragStart={this.checkpoint}
                                    onDragMove={e=>{const p=local(e.target.x(),e.target.y());this.editStroke(s=>{
                                        const node=s.curve?.nodes[i];if(node){node[axis]=p.x;node[axis+1]=p.y;}
                                    });}}/>
                            </Group>;
                        })}
                        <Circle name={`bezier-anchor-${i}`} x={anchor.x} y={anchor.y} radius={5/scale}
                            fill="white" stroke="#0284c7" strokeWidth={1.5/scale} draggable
                            onPointerDown={e=>{e.cancelBubble=true;}} onDragStart={this.checkpoint}
                            onDragMove={e=>{const p=local(e.target.x(),e.target.y());this.editStroke(s=>{
                                const node=s.curve?.nodes[i];if(node)moveNode(node,p.x,p.y);
                            });}}/>
                    </Group>;
                })}
            </Group>;
        }
        if (!o?.points?.length) return null;
        const stride=Math.max(1,Math.ceil(o.points.length/80)),scale=this.state.viewport.scale;
        return <Group>
            <Line points={o.points.flatMap(p=>{const w=strokePoint(o,p);return [w.x,w.y];})}
                stroke="#0ea5e9" strokeWidth={1.5/scale} dash={[4/scale,4/scale]} listening={false} />
            {o.points.map((p,i)=> {
                if (i%stride && i!==o.points!.length-1) return null;
                const w=strokePoint(o,p);
                return <Circle key={`${o.id}-${i}`} name={`stroke-handle-${i}`} x={w.x} y={w.y} radius={4/scale}
                    fill="white" stroke="#0284c7" strokeWidth={1.5/scale} draggable
                    onPointerDown={e=>{e.cancelBubble=true;}}
                    onDragStart={this.checkpoint}
                    onDragMove={e=>{
                        const x=e.target.x()-o.x,y=e.target.y()-o.y,r=-(o.rotation ?? 0)*Math.PI/180;
                        this.editStroke(s=>{if(s.points) s.points[i]={...s.points[i],x:x*Math.cos(r)-y*Math.sin(r),y:x*Math.sin(r)+y*Math.cos(r)};});
                    }} />;
            })}
        </Group>;
    };

    handleImageGenerated = async (imageUrl: string) => {
        this.setState({ assetError: undefined });
        try {
            const response = await fetch(imageUrl);
            if (!response.ok) throw new Error('无法读取生成图像');
            const blob = await response.blob();
            const imagePath = await this.storeImage(blob);
            const image = await createImageBitmap(blob);
            this.checkpoint();
            this.setState(state => produce(state, draft => {
                const layer = draft.layers.find(layer => layer.id === draft.activeLayer);
                if (layer && layer.visible && !layer.locked) {
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
                        image,
                        imagePath
                    });
                    draft.selectedObjectId = id;
                }
            }));
        } catch (error) {
            console.error('图片处理失败:', error);
            this.setState({ assetError: error instanceof Error ? error.message : '图像保存失败' });
        }
    };

    render() {
        if (this.state.restoring) return <div>正在恢复画布…</div>;
        if (this.state.restoreError) return <div role="alert">{this.state.restoreError}</div>;
        const { targetPosition, isDragging, layers, brushPosition, brushSize, contextMenu } = this.state;
        const viewport = this.state.viewport;
        const worldPos = this.state.worldPosition;
        const selectedLayer=layers.find(l=>l.id===this.state.activeLayer);
        const selected=selectedLayer?.objects.find(o=>o.id===this.state.selectedObjectId && o.type==='stroke');
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
                    touchAction: 'none',
                    background:'#ffffff'
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
                {this.state.assetError && <div role="alert" style={{ position: 'absolute', top: 8, left: 8, zIndex: 1000 }}>{this.state.assetError}</div>}
                <GpuCanvas layers={layers} width={viewport.size.width} height={viewport.size.height}
                    x={worldPos.x} y={worldPos.y} scale={viewport.scale} onBackend={this.handleBackend} onStats={this.handleCacheStats} />
                <div className="drawing-actions">
                    <span data-testid="render-backend" title={this.state.backendError}>{this.state.backend}</span>
                    {this.state.backend==='WebGPU' && <span data-testid="drawing-memory" title="GPU 缓存数据量估计，不含驱动开销和原始文档">{this.state.cacheTiles} 块 · {(this.state.cacheBytes/1048576).toFixed(2)} MiB</span>}
                    <button onClick={()=>this.fileInput.current?.click()}>导入图片</button>
                    <input ref={this.fileInput} data-testid="image-import" type="file" accept="image/*" hidden
                        onChange={e=>{const f=e.target.files?.[0];if(f) void this.importImage(f).catch(error=>this.setState({backendError:String(error)}));e.target.value='';}} />
                    <button onClick={this.undo} title="Ctrl+Z">撤销</button>
                    <button onClick={this.redo} title="Ctrl+Shift+Z">重做</button>
                    <select aria-label="笔触列表" value={this.state.selectedObjectId ?? ''}
                        onChange={e=>this.setState({selectedObjectId:e.target.value || null,selectedTool:'edit'})}>
                        <option value="">选择笔触</option>
                        {selectedLayer?.objects.filter(o=>o.type==='stroke').map((o,i)=><option key={o.id} value={o.id}
                            disabled={selectedLayer.locked || !selectedLayer.visible}>
                            {o.compositeOperation==='destination-out'?'橡皮擦':'笔触'} {i+1}
                        </option>)}
                    </select>
                    {selected && !selectedLayer?.locked && <>
                        <span data-testid="selected-stroke">{selected.curve ? `原 ${selected.curve.source_count} 点 · ${selected.curve.nodes.length} 锚点 · ${selected.curve.pressure.length} 压感点` : `已选笔触 · ${selected.points?.length} 点`}</span>
                        <select aria-label="笔触画笔类型" value={selected.strokeStyle ?? 'normal'}
                            onChange={e=>{const style=e.target.value as BrushStyle;this.checkpoint();this.editStroke(o=>{o.strokeStyle=style;});}}>
                            {BRUSHES.map(b=><option key={b.id} value={b.id}>{b.label}</option>)}
                        </select>
                        <label>线宽 <input aria-label="笔触线宽" type="number" min="1" max="500" value={selected.strokeWidth ?? 1}
                            onChange={e=>{const width=Number(e.target.value);if(width>0 && width<=500){this.checkpoint();this.editStroke(o=>{o.strokeWidth=width;});}}} /></label>
                        <input aria-label="笔触颜色" type="color" value={selected.stroke ?? '#1f2937'}
                            onChange={e=>{this.checkpoint();this.editStroke(o=>{o.stroke=e.target.value;});}} />
                        <button onClick={()=>{this.checkpoint();this.editStroke(o=>{vectorize(o);});}}>贝塞尔拟合</button>
                        <button onClick={()=>{this.checkpoint();this.editStroke(o=>{const sourceCount=o.curve?.source_count;o.points=smoothPoints(strokeSamples(o));delete o.curve;const curve=vectorize(o);if(curve&&sourceCount!==undefined)curve.source_count=sourceCount;});}}>平滑笔触</button>
                        <button onClick={()=>this.deleteObject(selectedLayer!.id,selected.id)}>删除笔触</button>
                        <small>白色锚点移动线条，紫色控制柄调整曲率</small>
                    </>}
                </div>
                <Stage
                    ref={this.stageRef}
                    width={viewport.size.width}
                    height={viewport.size.height}
                    draggable={false}
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
                    style={{position:'relative'}}
                >
                    <KonvaLayer>
                    {this.state.layers.map((layer) => (
                        <Group key={layer.id}>
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
                                                opacity={0}
                                                x={object.x}
                                                y={object.y}
                                                width={object.width}
                                                height={object.height}
                                                rotation={object.rotation ?? 0}
                                                draggable={this.state.selectedTool === 'move' && !layer.locked}
                                                onMouseDown={(e) => this.handleSelectObject(e, object.id)}
                                                onTap={(e) => this.handleSelectObject(e, object.id)}
                                                onDragEnd={(e) => this.handleImageDragEnd(e, object.id)}
                                                onDragStart={this.checkpoint}
                                                onDragMove={e=>{
                                                    const x=e.target.x(),y=e.target.y();
                                                    this.setState(s=>produce(s,d=>{const o=d.layers.find(l=>l.id===layer.id)?.objects.find(o=>o.id===object.id);if(o){o.x=x;o.y=y;}}));
                                                }}
                                                onTransformStart={this.checkpoint}
                                                onTransformEnd={(e) => this.handleTransformEnd(e, object.id)}
                                                onContextMenu={(e) => this.openObjectMenu(e, layer.id, object.id)}
                                                ref={(node) => this.registerImageNode(object.id, node)}
                                            />
                                        );
                                    }
                                    if (object.type === 'stroke') {
                                        return null;
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
                        </Group>
                    ))}
                    </KonvaLayer>
                    

                    <KonvaLayer name="editor-overlay">
                        {this.renderStrokeControls()}
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
                {!this.inputMode && <UIStateScope name="generation"><FloatingPanel path={this.props.path} aiDrawingService={this.drawingService}
                onSelectScript={this.handleSelectScript}
                onImageGenerated={this.handleImageGenerated}/></UIStateScope>}
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
