import { produce, immerable } from 'immer';

export class Viewport {
    [immerable] = true;
    
    public size: { width: number; height: number };
    public position: { x: number; y: number } = { x: 0, y: 0 };
    public scale: number = 1.0;
    public lastPointerPosition: { x: number; y: number } | null = null;
    public isDragging: boolean = false;

    constructor(width: number, height: number) {
        this.size = { width, height };
    }

    setSize(width: number, height: number) {
        return produce(this, draft => {
            draft.size = { width, height };
        });
    }

    isDraggingViewport(): boolean {
        return this.isDragging;
    }

    startDragging(pointerPosition: { x: number; y: number }) {
        return produce(this, draft => {
            draft.isDragging = true;
            draft.lastPointerPosition = { ...pointerPosition };
        });
    }

    stopDragging() {
        return produce(this, draft => {
            draft.isDragging = false;
            draft.lastPointerPosition = null;
        });
    }

    handleDrag(pointerPosition: { x: number; y: number }) {
        if (this.isDragging && this.lastPointerPosition) {
            const dx = pointerPosition.x - this.lastPointerPosition.x;
            const dy = pointerPosition.y - this.lastPointerPosition.y;
            
            return produce(this, draft => {
                draft.position = {
                    x: draft.position.x - dx,
                    y: draft.position.y - dy
                };
                draft.lastPointerPosition = { ...pointerPosition };
            });
        }
        return this;
    }

    handleZoom(deltaY: number, pointerPosition: { x: number; y: number }) {
        const oldScale = this.scale;
        const newScale = deltaY > 0 
            ? Math.max(0.1, oldScale * 0.9)
            : Math.min(4, oldScale * 1.1);
        
        const zoomPoint = {
            x: (pointerPosition.x - this.position.x),
            y: (pointerPosition.y - this.position.y)
        };

        const newX = pointerPosition.x - (zoomPoint.x * (newScale / oldScale));
        const newY = pointerPosition.y - (zoomPoint.y * (newScale / oldScale));
        
        return produce(this, draft => {
            draft.scale = newScale;
            draft.position = { x: newX, y: newY };
        });
    }

    /**
     * 以指定屏幕坐标（默认视口中心）为锚点按倍数缩放。
     */
    zoomBy(factor: number, center?: { x: number; y: number }) {
        const oldScale = this.scale;
        const newScale = Math.min(4, Math.max(0.1, oldScale * factor));
        if (newScale === oldScale) {
            return this;
        }

        const anchor = center ?? {
            x: this.size.width / 2,
            y: this.size.height / 2,
        };
        const actualFactor = newScale / oldScale;
        const zoomPoint = {
            x: anchor.x - this.position.x,
            y: anchor.y - this.position.y,
        };

        return produce(this, draft => {
            draft.scale = newScale;
            draft.position = {
                x: anchor.x - zoomPoint.x * actualFactor,
                y: anchor.y - zoomPoint.y * actualFactor,
            };
        });
    }

    /**
     * 重置视图：缩放恢复为 1，位置归零。
     */
    resetView() {
        return produce(this, draft => {
            draft.scale = 1;
            draft.position = { x: 0, y: 0 };
        });
    }
} 
