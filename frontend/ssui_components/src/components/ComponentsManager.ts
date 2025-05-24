import React from 'react';
import { IComponent } from './IComponent';
import { ComponentRefProps } from './ComponentRef';

export interface ComponentRegister {
    name: string;
    type: string;
    port: string;
    component: any;
    createComponent(ref: React.RefObject<IComponent>, params: ComponentRefProps): JSX.Element;
}

let components: { [key: string]: ComponentRegister } = {};

export function registerComponent(component: ComponentRegister) {
    components[component.name] = component;
    if (!component.createComponent)
        component.createComponent = (ref: React.RefObject<IComponent>, params: ComponentRefProps) => {
            console.log('Creating component', component.name, ref);
            let params_with_ref = { ...params, ref: ref };
            return React.createElement(component.component, params_with_ref);
        }
}

export function registerComponents(components: ComponentRegister[]) {
    components.forEach(c => registerComponent(c));
}

export function getComponent(name: string): ComponentRegister | undefined {
    return components[name];
}

export function getComponentsByType(type: string): ComponentRegister[] {
    return Object.values(components).filter(c => c.type === type);
}

/**
 * Python typing类型的接口定义
 */
export interface PythonType {
    type: string;           // 类型名称
    args?: PythonType[];    // 类型参数
}

/**
 * 使用递归下降解析器解析Python的typing类型
 * @param pythonType Python的typing类型字符串
 * @returns 解析后的Python typing结构
 */
export function parsePythonTyping(pythonType: string): PythonType {
    // 基本类型列表
    const basicTypes = ['int', 'float', 'str', 'bool', 'None', 'Any', 'Dict', 'List', 'Set', 'Tuple', 'Optional', 'Union', 'Callable'];

    // 如果已经是基本类型，直接返回
    if (basicTypes.includes(pythonType)) {
        return { type: pythonType };
    }

    // 使用递归下降解析器解析类型
    let index = 0;

    // 解析类型名称（包括点分隔符）
    function parseTypeName(): string {
        let name = '';
        while (index < pythonType.length && (/[a-zA-Z0-9_]/.test(pythonType[index]) || pythonType[index] === '.')) {
            name += pythonType[index];
            index++;
        }
        return name;
    }

    // 解析类型参数
    function parseTypeArgs(): PythonType[] {
        const args: PythonType[] = [];

        // 跳过左括号
        if (pythonType[index] === '[') {
            index++;
        } else {
            throw new Error(`Expected '[' at position ${index}`);
        }

        // 解析参数列表
        while (index < pythonType.length) {
            // 跳过空白字符
            while (index < pythonType.length && /\s/.test(pythonType[index])) {
                index++;
            }

            // 如果遇到右括号，结束解析
            if (pythonType[index] === ']') {
                index++;
                break;
            }

            // 解析一个类型参数
            const startIndex = index;
            let bracketCount = 0;

            while (index < pythonType.length) {
                if (pythonType[index] === '[') {
                    bracketCount++;
                } else if (pythonType[index] === ']') {
                    bracketCount--;
                    if (bracketCount < 0) {
                        break;
                    }
                } else if (pythonType[index] === ',' && bracketCount === 0) {
                    break;
                }
                index++;
            }

            const arg = pythonType.substring(startIndex, index).trim();
            args.push(parsePythonTyping(arg));

            // 如果遇到逗号，继续解析下一个参数
            if (pythonType[index] === ',') {
                index++;
            }
        }

        return args;
    }

    // 解析类型
    function parseType(): PythonType {
        // 解析类型名称
        const typeName = parseTypeName();

        // 如果遇到左括号，解析类型参数
        if (index < pythonType.length && pythonType[index] === '[') {
            const typeArgs = parseTypeArgs();
            return { type: typeName, args: typeArgs };
        }

        return { type: typeName };
    }

    // 开始解析
    return parseType();
}

