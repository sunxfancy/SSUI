import { Viewport } from '../canvas/Viewport';
import { WorldPosition } from '../canvas/WorldPosition';

describe('Viewport', () => {
  it('pans immutably while dragging', () => {
    const initial = new Viewport(800, 600);
    const dragging = initial.startDragging({ x: 100, y: 80 });
    const moved = dragging.handleDrag({ x: 140, y: 50 });

    expect(initial.isDragging).toBe(false);
    expect(moved.position).toEqual({ x: 40, y: -30 });
    expect(moved.lastPointerPosition).toEqual({ x: 140, y: 50 });
    expect(moved.stopDragging().lastPointerPosition).toBeNull();
  });

  it('keeps the world point under the cursor stable while zooming', () => {
    const initial = new Viewport(800, 600);
    const pointer = { x: 240, y: 180 };
    const before = {
      x: (pointer.x - initial.position.x) / initial.scale,
      y: (pointer.y - initial.position.y) / initial.scale,
    };

    const zoomed = initial.handleZoom(-1, pointer);
    const after = {
      x: (pointer.x - zoomed.position.x) / zoomed.scale,
      y: (pointer.y - zoomed.position.y) / zoomed.scale,
    };

    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
  });

  it('clamps zoom and resets position and scale', () => {
    let viewport = new Viewport(800, 600);
    for (let index = 0; index < 100; index += 1) viewport = viewport.zoomBy(2);
    expect(viewport.scale).toBe(4);
    for (let index = 0; index < 100; index += 1) viewport = viewport.zoomBy(0.5);
    expect(viewport.scale).toBe(0.1);
    expect(viewport.resetView()).toMatchObject({ scale: 1, position: { x: 0, y: 0 } });
  });
});

describe('WorldPosition', () => {
  it('moves and sets coordinates without mutating the previous value', () => {
    const initial = new WorldPosition(10, 20);
    const moved = initial.move(5, -3);
    expect(initial).toMatchObject({ x: 10, y: 20 });
    expect(moved).toMatchObject({ x: 15, y: 17 });
    expect(moved.setPosition(0, 0)).toMatchObject({ x: 0, y: 0 });
  });
});
