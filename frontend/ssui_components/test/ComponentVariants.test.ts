import React from 'react';
import { ComponentRef } from '../src/components/ComponentRef';
import { IComponent } from '../src/components/IComponent';
import { registerComponent, registerComponentVariant, resolveComponent, getComponentsByType, ComponentRegister } from '../src/components/ComponentsManager';

class BaseEditor extends IComponent<{}> {}
class VariantEditor extends IComponent<{}> { override onExecute() { return 'variant'; } }

describe('component variants', () => {
    const context = { name: 'VariantTestBase', type: 'test.variant', port: 'input', root_path: '', parameterName: 'special' };
    const cleanup: Array<() => void> = [];
    beforeAll(() => registerComponent({ name: context.name, type: context.type, port: 'input', component: BaseEditor } as ComponentRegister));
    afterEach(() => { cleanup.splice(0).forEach(dispose => dispose()); });

    it('resolves a registered variant from context and falls back to the base', () => {
        cleanup.push(registerComponentVariant({ name: 'test-special', base: context.name,
            matches: props => props.parameterName === 'special', component: VariantEditor }));
        expect(resolveComponent(context.name, context)?.component).toBe(VariantEditor);
        expect(resolveComponent(context.name, { ...context, parameterName: 'normal' })?.component).toBe(BaseEditor);
        expect(getComponentsByType(context.type, 'input').map(c => c.name)).toEqual([context.name]);
        expect(resolveComponent('missing', context)).toBeUndefined();
    });

    it('uses priority, stable ties, and unregisters variants', () => {
        cleanup.push(registerComponentVariant({ name: 'test-first', base: context.name, matches: () => true, component: VariantEditor }));
        cleanup.push(registerComponentVariant({ name: 'test-tie', base: context.name, matches: () => true, component: BaseEditor }));
        expect(resolveComponent(context.name, context)?.name).toBe('test-first');
        const dispose = registerComponentVariant({ name: 'test-priority', base: context.name, priority: 10, matches: () => true, component: BaseEditor });
        cleanup.push(dispose);
        expect(resolveComponent(context.name, context)?.name).toBe('test-priority');
        dispose();
        expect(resolveComponent(context.name, context)?.name).toBe('test-first');
    });

    it('keeps the ref and execution/update contract for variants and custom factories', () => {
        const factory = jest.fn((ref, props) => React.createElement(VariantEditor, { ...props, ref }));
        cleanup.push(registerComponentVariant({ name: 'test-factory', base: context.name, matches: () => true,
            component: VariantEditor, createComponent: factory }));
        const wrapper = new ComponentRef(context);
        wrapper.render();
        const [ref, props] = factory.mock.calls[0];
        expect(props).toBe(context);
        const instance = new VariantEditor({});
        ref.current = instance;
        expect(wrapper.onExecute()).toBe('variant');
        const update = jest.spyOn(instance, 'onUpdate');
        wrapper.onUpdate(123);
        expect(update).toHaveBeenCalledWith(123);
    });
});
