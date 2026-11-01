import '../src/components/InternalComponents';
import { getComponent, getComponentsByType } from '../src/components/ComponentsManager';
import { getController } from '../src/controllers/IController';

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
        expect(getComponent('Flux2KleinModelLoader')).toBeDefined();
        expect(getComponent('SD1LoraLoader')).toBeDefined();
        expect(getComponent('SDXLLoraLoader')).toBeDefined();
    });

    it('registers scalar editors and previews', () => {
        for (const type of ['builtins.str', 'builtins.int', 'builtins.float', 'builtins.bool']) {
            expect(getComponentsByType(type, 'input')).toHaveLength(1);
            expect(getComponentsByType(type, 'output')).toHaveLength(1);
        }
    });

    it('supports modern list aliases and typed fallbacks', () => {
        expect(getComponentsByType('builtins.list', 'input')[0]?.name).toBe('ListContainer');
        expect(getComponentsByType('typing.Dict', 'input')[0]?.name).toBe('JsonEditor');
        expect(getComponentsByType('typing.List', 'output')[0]?.name).toBe('JsonPreview');
        expect(getComponentsByType('typing.Optional', 'input')[0]?.name).toBe('OptionalContainer');
        expect(getComponentsByType('types.UnionType', 'input')[0]?.name).toBe('UnionTypeContainer');
    });

    it('registers backend media and workflow asset types', () => {
        expect(getComponent('AudioUploader')).toBeDefined();
        expect(getComponent('VoicePreview')).toBeDefined();
        expect(getComponent('MeshArtifact')).toBeDefined();
        expect(getComponent('MeshLoader')).toBeDefined();
        expect(getComponent('AgentPaintAssetLoader')).toBeDefined();
        expect(getComponent('PixelSrcAssetLoader')).toBeDefined();
        expect(getComponent('QwenImageModelLoader')).toBeDefined();
        expect(getComponent('QwenImageEditModelLoader')).toBeDefined();
        expect(getComponent('FluxLoraLoader')).toBeDefined();
    });

    it('registers the backend Input controller', () => {
        expect(getController('Input')).toBeDefined();
    });
});
