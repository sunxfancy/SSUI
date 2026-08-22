import React from 'react';
import {
    registerComponent,
    getComponent,
    getComponentsByType,
    ComponentRegister,
} from '../src/components/ComponentsManager';

function DummyComponent() {
    return React.createElement('div');
}

describe('ComponentsManager', () => {
    it('registers and retrieves a component by name', () => {
        registerComponent({
            name: 'TestComponent',
            type: 'ssui.base.Image',
            port: 'output',
            component: DummyComponent,
        } as unknown as ComponentRegister);

        const registered = getComponent('TestComponent');
        expect(registered).toBeDefined();
        expect(registered?.name).toBe('TestComponent');
        expect(registered?.type).toBe('ssui.base.Image');
    });

    it('fills in a default createComponent when missing', () => {
        const component = {
            name: 'NoFactoryComponent',
            type: 'ssui.base.Prompt',
            port: 'input',
            component: DummyComponent,
        } as unknown as ComponentRegister;

        registerComponent(component);

        expect(typeof component.createComponent).toBe('function');
        const element = component.createComponent(React.createRef(), {
            name: component.name,
            type: component.type,
            port: component.port,
            root_path: '',
        });
        expect(element).toBeDefined();
    });

    it('filters components by type', () => {
        registerComponent({
            name: 'ImagePickerLike',
            type: 'ssui.base.Image',
            port: 'output',
            component: DummyComponent,
        } as unknown as ComponentRegister);

        const byType = getComponentsByType('ssui.base.Image');
        expect(byType.length).toBeGreaterThanOrEqual(1);
        expect(byType.some((c) => c.type === 'ssui.base.Image')).toBe(true);
    });
});
