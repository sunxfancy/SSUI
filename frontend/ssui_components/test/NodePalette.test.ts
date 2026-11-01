import { filterPaletteItems, PALETTE_NODE_ITEMS } from '../src/shared/NodePalette';

describe('Flow node palette', () => {
    it('contains every creatable node kind', () => {
        expect(PALETTE_NODE_ITEMS.map(item => item.kind)).toEqual([
            'input', 'output', 'operator', 'definition', 'call',
        ]);
    });

    it('searches labels, descriptions and aliases case-insensitively', () => {
        expect(filterPaletteItems('模型').map(item => item.kind)).toEqual(['operator']);
        expect(filterPaletteItems('INPUT').map(item => item.kind)).toEqual(['input']);
        expect(filterPaletteItems('函数 复用').map(item => item.kind)).toEqual(['call']);
    });

    it('returns an empty result for an unknown query', () => {
        expect(filterPaletteItems('not-a-real-node')).toEqual([]);
    });
});
