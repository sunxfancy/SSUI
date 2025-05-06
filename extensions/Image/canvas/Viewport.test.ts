import { Viewport, ViewportState } from './Viewport';

describe('Viewport', () => {
    let viewport: Viewport;
    const initialState: ViewportState = {
        x: 0,
        y: 0,
        width: 1000,
        height: 1000,
        scale: 1
    };

    beforeEach(() => {
        viewport = new Viewport(initialState);
    });

    describe('初始状态', () => {
        it('应该正确初始化状态', () => {
            const state = viewport.getState();
            expect(state).toEqual(initialState);
        });

        it('初始时不应该处于拖动状态', () => {
            expect(viewport.isDraggingViewport()).toBe(false);
        });
    });

    describe('拖动功能', () => {
        it('应该能够开始拖动', () => {
            viewport.startDragging({ x: 100, y: 100 });
            expect(viewport.isDraggingViewport()).toBe(true);
        });

        it('应该能够停止拖动', () => {
            viewport.startDragging({ x: 100, y: 100 });
            viewport.stopDragging();
            expect(viewport.isDraggingViewport()).toBe(false);
        });

        it('拖动时应该正确更新位置', () => {
            viewport.startDragging({ x: 100, y: 100 });
            viewport.handleDrag({ x: 200, y: 200 });
            
            const state = viewport.getState();
            expect(state.x).toBe(-100);  // 世界反向移动
            expect(state.y).toBe(-100);
        });

        it('未开始拖动时不应该更新位置', () => {
            viewport.handleDrag({ x: 200, y: 200 });
            
            const state = viewport.getState();
            expect(state.x).toBe(0);
            expect(state.y).toBe(0);
        });

        it('停止拖动后不应该更新位置', () => {
            viewport.startDragging({ x: 100, y: 100 });
            viewport.stopDragging();
            viewport.handleDrag({ x: 200, y: 200 });
            
            const state = viewport.getState();
            expect(state.x).toBe(0);
            expect(state.y).toBe(0);
        });
    });

    describe('缩放功能', () => {
        it('应该能够放大', () => {
            viewport.handleZoom(-100, { x: 500, y: 500 });
            const state = viewport.getState();
            expect(state.scale).toBeGreaterThan(1);
        });

        it('应该能够缩小', () => {
            viewport.handleZoom(100, { x: 500, y: 500 });
            const state = viewport.getState();
            expect(state.scale).toBeLessThan(1);
        });

        it('缩放比例应该在有效范围内', () => {
            // 多次放大
            for (let i = 0; i < 10; i++) {
                viewport.handleZoom(-100, { x: 500, y: 500 });
            }
            const maxScaleState = viewport.getState();
            expect(maxScaleState.scale).toBeLessThanOrEqual(4);

            // 多次缩小
            for (let i = 0; i < 10; i++) {
                viewport.handleZoom(100, { x: 500, y: 500 });
            }
            const minScaleState = viewport.getState();
            expect(minScaleState.scale).toBeGreaterThanOrEqual(0.1);
        });

        it('缩放时应该保持鼠标位置不变', () => {
            const mousePosition = { x: 500, y: 500 };
            viewport.handleZoom(-100, mousePosition);
            
            const state = viewport.getState();
            // 计算缩放后的鼠标位置
            const scaledX = (mousePosition.x - state.x) / state.scale;
            const scaledY = (mousePosition.y - state.y) / state.scale;
            
            // 鼠标位置应该大致保持不变（允许一些浮点数误差）
            expect(Math.abs(scaledX - 500)).toBeLessThan(0.1);
            expect(Math.abs(scaledY - 500)).toBeLessThan(0.1);
        });
    });

    describe('组合操作', () => {
        it('拖动和缩放应该能够正确组合', () => {
            // 先拖动
            viewport.startDragging({ x: 100, y: 100 });
            viewport.handleDrag({ x: 200, y: 200 });
            
            const draggedState = viewport.getState();
            expect(draggedState.x).toBe(-100);  // 世界反向移动
            expect(draggedState.y).toBe(-100);
            
            // 然后缩放
            viewport.handleZoom(-100, { x: 500, y: 500 });
            
            const finalState = viewport.getState();
            expect(finalState.scale).toBeGreaterThan(1);
            // 确保位置在缩放后仍然正确
            expect(finalState.x).not.toBe(draggedState.x); // 位置会因为缩放而改变
            expect(finalState.y).not.toBe(draggedState.y);
        });

        it('缩放后拖动应该保持正确的相对位置', () => {
            // 先缩放
            viewport.handleZoom(-100, { x: 500, y: 500 });
            const scaleState = viewport.getState();
            const scale = scaleState.scale;
            
            // 记录缩放后的位置
            const startX = scaleState.x;
            const startY = scaleState.y;
            
            // 然后拖动
            viewport.startDragging({ x: 100, y: 100 });
            viewport.handleDrag({ x: 200, y: 200 });
            
            const finalState = viewport.getState();
            // 位置应该移动100个单位（世界反向移动）
            expect(finalState.x).toBe(startX - 100);
            expect(finalState.y).toBe(startY - 100);
            expect(finalState.scale).toBe(scale);
        });
    });
}); 