export interface ComponentRegister {
    name: string;
    type: string;
    port: string;
    component: any;
    createComponent(ref: React.RefObject<IComponent>): JSX.Element;
}

import React from 'react';
import { IComponent } from './IComponent';

let components: { [key: string]: ComponentRegister } = {};

export function registerComponent(component: ComponentRegister) {
    components[component.name] = component;
    if (!component.createComponent)
        component.createComponent = (ref: React.RefObject<IComponent>) => {
            console.log('Creating component', component.name, ref);
            return React.createElement(component.component, {ref: ref});
        }
}

export function registerComponents(components: ComponentRegister[]) {
    components.forEach(c => registerComponent(c));
}

export function getComponent(name: string): ComponentRegister | undefined {
    return components[name];
}

export function getComponentsByType(type: string): ComponentRegister[] {
    return Object.values(components).filter(c => c.type === type);
}