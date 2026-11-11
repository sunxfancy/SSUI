import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import '../src/components/InternalComponents';
import { getComponent } from '../src/components/ComponentsManager';
import { loraParams, LoraFields } from '../src/components/Loader/LoraFields';

function loader(name: string) {
    const registered = getComponent(name);
    expect(registered).toBeDefined();
    return new registered!.component({});
}

describe('LoRA model panels', () => {
    it.each(['WanVideoModelLoader', 'Wan2T2VModelLoader', 'Wan2I2VModelLoader',
        'Wan21T2V13BModelLoader', 'Wan22TI2VModelLoader', 'CogVideoModelLoader',
        'HunyuanVideoModelLoader', 'HunyuanImageToVideoModelLoader', 'AnimateDiffModelLoader',
        'Wan21ModelLoader', 'CogVideo2BModelLoader', 'QwenImageModelLoader', 'Flux2KleinModelLoader'])
    ('sends optional adapter settings for %s', name => {
        const panel = loader(name);
        panel.state = { ...panel.state, values: { model_path: 'models/base' },
            loraPath: 'models/adapter.safetensors', loraWeight: -0.5 };
        expect(panel.onExecute().params).toMatchObject({ lora_path: 'models/adapter.safetensors', lora_weight: -0.5 });
        expect(panel.persistedFields).toEqual(expect.arrayContaining(['loraPath', 'loraWeight']));
    });

    it.each(['Wan22T2VA14BModelLoader', 'Wan22I2VA14BModelLoader'])
    ('keeps high and low noise adapters separate for %s', name => {
        const panel = loader(name);
        panel.state = { ...panel.state, loraPath: 'high.safetensors', loraWeight: 0.3,
            lowPath: 'low.safetensors', lowWeight: 0.7 };
        expect(panel.onExecute().params).toEqual({ high_noise_lora_path: 'high.safetensors',
            high_noise_lora_weight: 0.3, low_noise_lora_path: 'low.safetensors', low_noise_lora_weight: 0.7 });
        expect(renderToStaticMarkup(panel.render())).toContain('高噪声 LoRA');
        expect(renderToStaticMarkup(panel.render())).toContain('低噪声 LoRA');
    });

    it('rejects invalid weights and renders optional file controls', () => {
        expect(() => loraParams('', NaN)).toThrow('LoRA');
        expect(loraParams('  ', 1)).toEqual({ lora_path: '', lora_weight: 1 });
        const html = renderToStaticMarkup(React.createElement(LoraFields, {
            path: 'adapter.safetensors', weight: 0.8, onPath: () => {}, onWeight: () => {} }));
        expect(html).toContain('adapter.safetensors');
        expect(html).toContain('LoRA 权重');
    });
});
