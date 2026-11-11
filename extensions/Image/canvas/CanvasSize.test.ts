import { alphaBounds, paddedBounds } from './CanvasSize';

test('pads every edge and rounds dimensions upward to 64, including negative coordinates', () => {
    expect(paddedBounds({ x: -100, y: 10, width: 101, height: 64 }, 10)).toEqual({ x: -114, y: -22, width: 128, height: 128 });
});
test('empty canvas has a nonzero aligned output', () => {
    expect(paddedBounds(null, 0)).toEqual({ x: -32, y: -32, width: 64, height: 64 });
    expect(paddedBounds(null, 40).width).toBe(128);
});
test('bounds use actual alpha, excluding erased and transparent pixels', () => {
    const data = new Uint8ClampedArray(4 * 4 * 4);
    expect(alphaBounds(data, 4, 4)).toBeNull();
    data[(1 * 4 + 2) * 4 + 3] = 1;
    expect(alphaBounds(data, 4, 4)).toEqual({ x: 2, y: 1, width: 1, height: 1 });
});
