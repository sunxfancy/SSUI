import { getComponentsByType, resolveComponent } from '../src/components/ComponentsManager';
import { Pixal3DImageUploader, Pixal3DModelLoader, Trellis2ModelLoader, TrellisModelLoader } from '../src/components/Loader/Pixal3DLoader';

describe('Pixal3D workflow inputs', () => {
    it('registers TRELLIS model inputs with supported loading options', () => {
        for (const [type, Loader, lowVram] of [
            ['Trellis2.Trellis2Model', Trellis2ModelLoader, true],
            ['Trellis.TrellisModel', TrellisModelLoader, false],
        ] as const) {
            expect(getComponentsByType(`ssui_3dmodel.${type}`, 'input')
                .some(component => component.component === Loader)).toBe(true);
            const loader = new Loader({});
            expect(loader.onExecute()).toEqual({ function: `ssui_3dmodel.${type}.load`,
                params: { model_path: loader.state.modelPath, ...(lowVram ? { low_vram: true } : {}) } });
        }
        for (const name of ['trellis', 'trellis2']) {
            expect(resolveComponent('ImageUploader', { name: 'ImageUploader', type: 'ssui.base.Image',
                port: 'input', root_path: '', script_path: `/examples/workflow-${name}.py` })?.component)
                .toBe(Pixal3DImageUploader);
        }
    });
    it('registers the model input with a GPU model descriptor', () => {
        expect(getComponentsByType('ssui_3dmodel.Pixal3D.Pixal3DModel', 'input')
            .some(component => component.name === 'Pixal3DModelLoader')).toBe(true);
        const loader = new Pixal3DModelLoader({});
        loader.state = { modelPath: 'C:/models/Pixal3D', lowVram: true };
        expect(loader.onExecute()).toEqual({
            function: 'ssui_3dmodel.Pixal3D.Pixal3DModel.load',
            params: { model_path: 'C:/models/Pixal3D', low_vram: true },
        });
    });

    it('preserves alpha only for the focused Pixal3D workflow uploader', () => {
        const context = { name: 'ImageUploader', type: 'ssui.base.Image', port: 'input',
            root_path: '', script_path: 'C:\\examples\\workflow-pixal3d.py' };
        expect(resolveComponent('ImageUploader', context)?.component).toBe(Pixal3DImageUploader);
        expect(resolveComponent('ImageUploader', { ...context, script_path: '/examples/workflow-sd1.py' })?.component)
            .not.toBe(Pixal3DImageUploader);
        const uploader = new Pixal3DImageUploader({ script_path: context.script_path });
        uploader.state = { image: '/input.png', uploading: false, error: null };
        expect(uploader.onExecute()).toEqual({ function: 'ssui_3dmodel.Pixal3D.LoadPixal3DImage', params: { path: '/input.png' } });
    });
});
