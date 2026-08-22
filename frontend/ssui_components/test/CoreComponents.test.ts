import '../src/components/InternalComponents';
import { getComponent, getComponentsByType } from '../src/components/ComponentsManager';

describe('Core Functional UI components', () => {
    it('registers ListContainer for typing.List', () => {
        const list = getComponent('ListContainer');
        expect(list).toBeDefined();
        expect(list?.type).toBe('typing.List');
    });

    it('registers image upload / picker / preview components', () => {
        expect(getComponent('ImageUploader')).toBeDefined();
        expect(getComponent('ImagePicker')).toBeDefined();
        expect(getComponent('ImagePreview')).toBeDefined();
        expect(getComponentsByType('ssui.base.Image').length).toBeGreaterThanOrEqual(3);
    });

    it('registers SD1 / SDXL / Flux model loaders', () => {
        expect(getComponent('SD1ModelLoader')).toBeDefined();
        expect(getComponent('SDXLModelLoader')).toBeDefined();
        expect(getComponent('FluxModelLoader')).toBeDefined();
        expect(getComponent('SD1LoraLoader')).toBeDefined();
        expect(getComponent('SDXLLoraLoader')).toBeDefined();
    });
});
