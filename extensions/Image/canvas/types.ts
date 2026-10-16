import type React from 'react';
import type { BrushStyle } from './brushes';

export interface DrawableObject {
    id: string;
    type: string;
    x: number;
    y: number;
    obj?: React.ReactNode;
    name?: string;
    width?: number;
    height?: number;
    rotation?: number;
    image?: ImageBitmap;
    points?: StrokePoint[];
    curve?: CurvePath;
    stroke?: string;
    strokeWidth?: number;
    strokeStyle?: BrushStyle;
    feather?: number;
    compositeOperation?: 'source-over' | 'destination-out';
}

export type BezierNode = [x: number, y: number, inX: number, inY: number, outX: number, outY: number, t: number];
export interface CurvePath {
    nodes: BezierNode[];
    pressure: [t: number, pressure: number][];
    source_count: number;
    tolerance: number;
}

export interface StrokePoint {
    x: number;
    y: number;
    pressure: number;
}

export interface Layer {
    id: string;
    name: string;
    visible: boolean;
    locked: boolean;
    opacity: number;
    objects: DrawableObject[];
}
