export type BrushStyle = 'normal' | 'pen' | 'marker' | 'watercolor' | 'pencil' | 'airbrush' | 'texture';
export const BRUSHES: { id: BrushStyle; label: string; size: number; description: string }[] = [
    { id: 'normal', label: '常规', size: 20, description: '圆头实色线条，笔压控制粗细' },
    { id: 'pen', label: '钢笔', size: 8, description: '细腻实色墨迹，笔压变化更灵敏' },
    { id: 'marker', label: '马克笔', size: 28, description: '平头宽幅、半透明叠色' },
    { id: 'watercolor', label: '水彩笔', size: 48, description: '柔和边缘、色素沉积和纸面纹理' },
    { id: 'pencil', label: '铅笔', size: 5, description: '细颗粒、纸纹留白和干涩边缘' },
    { id: 'airbrush', label: '喷枪', size: 40, description: '柔和渐变喷涂' },
    { id: 'texture', label: '纹理', size: 20, description: '粗颗粒纹理笔触' },
];
export function brushPressure(style: BrushStyle | undefined, p: number) {
    if (style === 'pen') return Math.pow(Math.max(0.01, p), 0.7);
    if (style === 'marker') return 0.8 + 0.2 * p;
    if (style === 'pencil') return 0.3 + 0.7 * p;
    return Math.max(0.01, p);
}
