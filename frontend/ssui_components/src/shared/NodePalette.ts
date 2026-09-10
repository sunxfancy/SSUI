export type PaletteNodeKind = 'input' | 'output' | 'operator' | 'definition' | 'call';

export interface PaletteNodeItem {
    kind: PaletteNodeKind;
    label: string;
    description: string;
    group: '结构' | '函数';
    keywords: string[];
}

export const PALETTE_NODE_ITEMS: PaletteNodeItem[] = [
    { kind: 'input', label: '输入', description: '声明工作流的输入参数', group: '结构', keywords: ['input', '参数', '入口'] },
    { kind: 'output', label: '返回', description: '声明工作流的返回值', group: '结构', keywords: ['output', '结果', '出口'] },
    { kind: 'operator', label: '算子', description: '调用 Python 函数或模型能力', group: '函数', keywords: ['operator', 'node', '模型', '调用'] },
    { kind: 'definition', label: '函数定义', description: '把一组节点封装成函数', group: '函数', keywords: ['function', 'definition', '分组', '封装'] },
    { kind: 'call', label: '函数调用', description: '调用画布中已有的函数定义', group: '函数', keywords: ['function', 'call', '复用', '引用'] },
];

export function filterPaletteItems(query: string, items = PALETTE_NODE_ITEMS): PaletteNodeItem[] {
    const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return items;
    return items.filter((item) => {
        const haystack = [item.label, item.description, item.group, ...item.keywords]
            .join(' ')
            .toLocaleLowerCase();
        return terms.every((term) => haystack.includes(term));
    });
}
