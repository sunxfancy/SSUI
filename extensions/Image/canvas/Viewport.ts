export interface ViewportState {
    x: number;
    y: number;
    width: number;
    height: number;
    scale: number;
}

export class Viewport {
    private state: ViewportState;
    private lastPointerPosition: { x: number; y: number } | null = null;
    private isDragging: boolean = false;

    constructor(initialState: ViewportState) {
        this.state = initialState;
    }

    getState(): ViewportState {
        return { ...this.state };
    }

    isDraggingViewport(): boolean {
        return this.isDragging;
    }

    startDragging(pointerPosition: { x: number; y: number }) {
        this.isDragging = true;
        this.lastPointerPosition = { ...pointerPosition };
    }

    stopDragging() {
        this.isDragging = false;
        this.lastPointerPosition = null;
    }

    handleDrag(pointerPosition: { x: number; y: number }) {
        if (this.isDragging && this.lastPointerPosition) {
            // 计算鼠标移动的距离
            const dx = pointerPosition.x - this.lastPointerPosition.x;
            const dy = pointerPosition.y - this.lastPointerPosition.y;
            
            // 更新视口位置，使世界相对于窗口移动
            this.state = {
                ...this.state,
                x: this.state.x - dx,
                y: this.state.y - dy
            };
            
            // 更新最后的指针位置
            this.lastPointerPosition = { ...pointerPosition };
            return true;
        }
        return false;
    }

    handleZoom(deltaY: number, pointerPosition: { x: number; y: number }) {
        const oldScale = this.state.scale;
        
        // 计算新的缩放比例
        const newScale = deltaY > 0 
            ? Math.max(0.1, oldScale * 0.9)
            : Math.min(4, oldScale * 1.1);
        
        // 计算缩放中心相对于视口原点的位置
        const zoomPoint = {
            x: (pointerPosition.x - this.state.x),
            y: (pointerPosition.y - this.state.y)
        };

        // 计算新的位置，保持鼠标指针位置不变
        const newX = pointerPosition.x - (zoomPoint.x * (newScale / oldScale));
        const newY = pointerPosition.y - (zoomPoint.y * (newScale / oldScale));
        
        this.state = {
            ...this.state,
            scale: newScale,
            x: newX,
            y: newY
        };
    }
} 