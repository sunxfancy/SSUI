import React from 'react';
import { Stage, Layer, Rect, Line, Group } from 'react-konva';
import { AIDrawingService, MockAIDrawingService } from './AIDrawingService';

const BLOCK_SIZE = 512;
const GRID_SIZE = 64;
const CANVAS_SIZE = 1024;
const TARGET_SIZE = 512;

// 空间哈希函数，将坐标转换为块索引
const getBlockHash = (x: number, y: number): string => {
    const blockX = Math.floor(x / BLOCK_SIZE);
    const blockY = Math.floor(y / BLOCK_SIZE);
    return `${blockX},${blockY}`;
};

// 获取块的世界坐标
const getBlockWorldPosition = (blockHash: string): { x: number; y: number } => {
    const [blockX, blockY] = blockHash.split(',').map(Number);
    return {
        x: blockX * BLOCK_SIZE,
        y: blockY * BLOCK_SIZE
    };
};

interface GridProps {
    size: number;
    blockHash: string;
    viewport: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
}

class Grid extends React.Component<GridProps> {
    render() {
        const { size, blockHash, viewport } = this.props;
        const blockPos = getBlockWorldPosition(blockHash);
        
        // 计算需要显示的网格范围
        const startX = Math.floor((viewport.x - blockPos.x) / size) * size;
        const startY = Math.floor((viewport.y - blockPos.y) / size) * size;
        const endX = Math.ceil((viewport.x + viewport.width - blockPos.x) / size) * size;
        const endY = Math.ceil((viewport.y + viewport.height - blockPos.y) / size) * size;

        const lines = [];
        for (let x = startX; x <= endX; x += size) {
            lines.push(
                <Line
                    key={`v-${x}`}
                    points={[x, startY, x, endY]}
                    stroke="#ccc"
                    strokeWidth={1}
                />
            );
        }
        for (let y = startY; y <= endY; y += size) {
            lines.push(
                <Line
                    key={`h-${y}`}
                    points={[startX, y, endX, y]}
                    stroke="#ccc"
                    strokeWidth={1}
                />
            );
        }
        return <>{lines}</>;
    }
}

interface AIDrawingCanvasState {
    targetPosition: {
        x: number;
        y: number;
    };
    isDragging: boolean;
    isViewportDragging: boolean;
    viewport: {
        x: number;
        y: number;
        width: number;
        height: number;
        scale: number;
    };
    lastPointerPosition: {
        x: number;
        y: number;
    } | null;
}

class AIDrawingCanvas extends React.Component<{}, AIDrawingCanvasState> {
    private drawingService: AIDrawingService;
    private visibleBlocks: Set<string>;
    private stageRef: React.RefObject<any>;

    constructor(props: {}) {
        super(props);
        this.state = {
            targetPosition: { x: 0, y: 0 },
            isDragging: false,
            isViewportDragging: false,
            viewport: {
                x: 0,
                y: 0,
                width: CANVAS_SIZE,
                height: CANVAS_SIZE,
                scale: 1
            },
            lastPointerPosition: null
        };
        this.drawingService = new MockAIDrawingService();
        this.visibleBlocks = new Set();
        this.stageRef = React.createRef();
    }

    componentDidMount() {
        this.drawingService.initialize();
        this.updateVisibleBlocks();
    }

    // 更新可见块
    private updateVisibleBlocks = () => {
        const { viewport } = this.state;
        const blocks = new Set<string>();
        
        // 计算视口覆盖的块
        const startBlockX = Math.floor(viewport.x / BLOCK_SIZE);
        const startBlockY = Math.floor(viewport.y / BLOCK_SIZE);
        const endBlockX = Math.ceil((viewport.x + viewport.width / viewport.scale) / BLOCK_SIZE);
        const endBlockY = Math.ceil((viewport.y + viewport.height / viewport.scale) / BLOCK_SIZE);

        for (let x = startBlockX; x <= endBlockX; x++) {
            for (let y = startBlockY; y <= endBlockY; y++) {
                blocks.add(`${x},${y}`);
            }
        }
        
        this.visibleBlocks = blocks;
        this.forceUpdate();
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
            
            this.setState({
                isViewportDragging: true,
                lastPointerPosition: {
                    x: pointer.x,
                    y: pointer.y
                }
            });
        }
    };

    handleViewportDragMove = (e: any) => {
        if (this.state.isViewportDragging && this.state.lastPointerPosition) {
            const stage = this.stageRef.current;
            const pointer = stage.getPointerPosition();
            
            const dx = pointer.x - this.state.lastPointerPosition.x;
            const dy = pointer.y - this.state.lastPointerPosition.y;
            
            this.setState(prevState => ({
                viewport: {
                    ...prevState.viewport,
                    x: prevState.viewport.x + dx,
                    y: prevState.viewport.y + dy
                },
                lastPointerPosition: {
                    x: pointer.x,
                    y: pointer.y
                }
            }), this.updateVisibleBlocks);
        }
    };

    handleViewportDragEnd = () => {
        this.setState({
            isViewportDragging: false,
            lastPointerPosition: null
        });
    };

    // 处理鼠标滚轮缩放
    handleWheel = (e: any) => {
        e.evt.preventDefault();
        
        const stage = this.stageRef.current;
        const oldScale = this.state.viewport.scale;
        const pointer = stage.getPointerPosition();
        
        // 计算鼠标相对于视口的位置
        const mousePointTo = {
            x: (pointer.x - this.state.viewport.x) / oldScale,
            y: (pointer.y - this.state.viewport.y) / oldScale,
        };
        
        // 计算新的缩放比例
        const newScale = e.evt.deltaY > 0 
            ? Math.max(0.1, oldScale * 0.9)
            : Math.min(4, oldScale * 1.1);
        
        this.setState(prevState => ({
            viewport: {
                ...prevState.viewport,
                scale: newScale,
                x: pointer.x - mousePointTo.x * newScale,
                y: pointer.y - mousePointTo.y * newScale
            }
        }), this.updateVisibleBlocks);
    };

    render() {
        const { targetPosition, isDragging, viewport } = this.state;

        return (
            <div style={{ 
                padding: '0',
                margin: '0',
                width: '100vw',
                height: '100vh',
                overflow: 'hidden',
                position: 'fixed',
                top: 0,
                left: 0,
                cursor: this.state.isViewportDragging ? 'grabbing' : 'grab'
            }}>
                <Stage
                    ref={this.stageRef}
                    width={window.innerWidth}
                    height={window.innerHeight}
                    draggable={this.state.isViewportDragging}
                    onMouseDown={this.handleViewportDragStart}
                    onMouseMove={this.handleViewportDragMove}
                    onMouseUp={this.handleViewportDragEnd}
                    onWheel={this.handleWheel}
                    onContextMenu={(e) => e.evt.preventDefault()}
                    scaleX={viewport.scale}
                    scaleY={viewport.scale}
                    x={viewport.x}
                    y={viewport.y}
                >
                    <Layer>
                        {/* 渲染所有可见块 */}
                        {Array.from(this.visibleBlocks).map(blockHash => (
                            <Group key={blockHash}>
                                <Grid
                                    size={GRID_SIZE}
                                    blockHash={blockHash}
                                    viewport={viewport}
                                />
                            </Group>
                        ))}
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
            </div>
        );
    }
}

export default AIDrawingCanvas;
