import type React from 'react';

export interface DrawableObject {
    type: string;
    x: number;
    y: number;
    obj: React.ReactNode;
}

export interface Layer {
    id: string;
    name: string;
    visible: boolean;
    locked: boolean;
    opacity: number;
    objects: DrawableObject[];
}
