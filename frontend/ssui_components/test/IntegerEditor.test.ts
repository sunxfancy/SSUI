import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ComponentTabRef } from '../src/components/ComponentRef';
import { RandomIntegerEditor } from '../src/components/Base/RandomIntegerEditor';
import { IntegerEditor } from '../src/components/Base/ScalarComponents';
import { resolveComponent } from '../src/components/ComponentsManager';

describe('seed integer variant', () => {
    it('passes the parameter name through component selection and shows a dice button', () => {
        const render = (name: string, type = 'builtins.int') => renderToStaticMarkup(
            React.createElement(ComponentTabRef, { name, type, port: 'input', root_path: '' })
        );
        expect(render('seed')).toContain('aria-label="随机生成 seed"');
        expect(render('seed', 'int')).toContain('aria-label="随机生成 seed"');
        expect(render('steps')).not.toContain('随机生成 seed');
        expect(render('seed', 'builtins.float')).not.toContain('随机生成 seed');
        expect(resolveComponent('IntegerEditor', {
            name: 'IntegerEditor', parameterName: 'steps', type: 'builtins.int', port: 'input', root_path: '',
        })?.component).toBe(IntegerEditor);
    });

    it('submits the displayed random value and preserves manually entered integers', () => {
        const editor = new RandomIntegerEditor({});
        editor.setState = (update: any) => { Object.assign(editor.state, update); };
        const random = jest.spyOn(Math, 'random').mockReturnValue(0.123456789);
        try {
            editor.generateRandom();
            expect(editor.state.value).toBe(123456789);
            expect(editor.onExecute()).toBe(editor.state.value);
            expect(editor.onExecute()).toBe(123456789);
            editor.setState({ value: 42 });
            expect(editor.onExecute()).toBe(42);
        } finally {
            random.mockRestore();
        }
    });
});
