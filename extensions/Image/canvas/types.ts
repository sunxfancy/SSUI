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
}

export interface Layer {
    id: string;
    name: string;
    visible: boolean;
    locked: boolean;
    opacity: number;
    objects: DrawableObject[];
}
