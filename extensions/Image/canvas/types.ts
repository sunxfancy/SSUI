import type React from 'react';

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
    stroke?: string;
    strokeWidth?: number;
    strokeStyle?: 'normal' | 'airbrush' | 'texture';
    feather?: number;
    compositeOperation?: 'source-over' | 'destination-out';
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
