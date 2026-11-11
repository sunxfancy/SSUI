export interface CanvasSettings { unbounded: boolean; width: number; height: number; margin: number }
export interface Bounds { x: number; y: number; width: number; height: number }

export function paddedBounds(bounds: Bounds | null, margin: number): Bounds {
    const width = Math.max(64, Math.ceil(((bounds?.width ?? 0) + margin * 2) / 64) * 64);
    const height = Math.max(64, Math.ceil(((bounds?.height ?? 0) + margin * 2) / 64) * 64);
    return { x: Math.floor((bounds?.x ?? 0) - (width - (bounds?.width ?? 0)) / 2),
        y: Math.floor((bounds?.y ?? 0) - (height - (bounds?.height ?? 0)) / 2), width, height };
}

export function alphaBounds(data: Uint8ClampedArray, width: number, height: number): Bounds | null {
    let left = width, top = height, right = -1, bottom = -1;
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        if (data[(y * width + x) * 4 + 3] === 0) continue;
        left = Math.min(left, x); top = Math.min(top, y);
        right = Math.max(right, x); bottom = Math.max(bottom, y);
    }
    return right < 0 ? null : { x: left, y: top, width: right - left + 1, height: bottom - top + 1 };
}
