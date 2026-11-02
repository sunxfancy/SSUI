import React from 'react';
import { Button } from '@blueprintjs/core';
import { IntegerEditor } from './ScalarComponents';
import { registerComponentVariant } from '../ComponentsManager';

export class RandomIntegerEditor extends IntegerEditor {
    generateRandom = () => {
        this.setState({ value: Math.floor(Math.random() * 1000000000) });
    };

    override render() {
        return <div className="component-integer-random">
            {super.render()}
            <Button type="button" minimal small aria-label="随机生成 seed" title="随机生成 seed"
                onClick={this.generateRandom}><span aria-hidden="true">⚄</span></Button>
        </div>;
    }
}

registerComponentVariant({
    name: 'RandomIntegerEditor',
    base: 'IntegerEditor',
    matches: context => context.parameterName === 'seed',
    component: RandomIntegerEditor,
});
