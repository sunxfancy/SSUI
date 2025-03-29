import React from 'react';

export type IControlerProps = {
    name: string,
    params: any;
    default: any;
};

export interface IControler<S = {}> extends React.Component<IControlerProps, S> {}
export class IControler<S> extends React.Component<IControlerProps, S> {
    onExecute(): any {}
}


export interface ControlerRegister {
    name: string;
    component: any;
    createControler(params: any, def: any, ref: React.RefObject<IControler>): JSX.Element;
}

let controlers: { [key: string]: ControlerRegister } = {};

export function registerControler(component: ControlerRegister) {
    controlers[component.name] = component;
    if (!component.createControler)
        component.createControler = (params: any, def: any, ref: React.RefObject<IControler>) => {
            console.log('Creating controler', component.name, ref);
            return React.createElement(component.component, {params: params, default: def, ref: ref});
        }
}

export function registerControlers(controlers: ControlerRegister[]) {
    controlers.forEach(c => registerControler(c));
}

export function getControler(name: string): ControlerRegister | undefined {
    return controlers[name];
}

