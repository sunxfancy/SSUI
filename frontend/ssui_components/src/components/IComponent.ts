import React from 'react';
import { PersistentComponent } from '../UIState';

export class IComponent<P = {}, S = {}> extends PersistentComponent<P, S> {
    onExecute(): any {}
    onUpdate(data: any): void {}
}