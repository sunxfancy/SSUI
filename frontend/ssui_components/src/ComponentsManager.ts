export interface ComponentRegister {
    name: string;
    type: string;
    port: string;
    component: any;
}

let components: { [key : string] : ComponentRegister } = {};

export function registerComponent(component: ComponentRegister) {
    components[component.name] = component;
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