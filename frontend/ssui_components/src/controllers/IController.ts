import React from 'react';
import { PersistentComponent } from '../UIState';

export type IControllerProps = {
    name: string,
    params: any;
    default: any;
};

export class IController<S = {}> extends PersistentComponent<IControllerProps, S> {
    protected persistedFields = ['value', 'userInput'] as (keyof S)[];
    onExecute(): any {}
}


export interface ControllerRegister {
    name: string;
    component: any;
    createController(params: any, def: any, ref: React.RefObject<IController>): JSX.Element;
}

let controllers: { [key: string]: ControllerRegister } = {};

export function registerController(component: ControllerRegister) {
    controllers[component.name] = component;
    if (!component.createController)
        component.createController = (params: any, def: any, ref: React.RefObject<IController>) => {
            console.log('Creating controller', component.name, ref);
            return React.createElement(component.component, {params: params, default: def, ref: ref});
        }
}

export function registerControllers(controllers: ControllerRegister[]) {
    controllers.forEach(c => registerController(c));
}

export function getController(name: string): ControllerRegister | undefined {
    return controllers[name];
}

