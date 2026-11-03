import React from 'react';
import { FormGroup, InputGroup, NumericInput } from '@blueprintjs/core';

export function loraParams(path: string, weight: number, prefix = '') {
    if (!Number.isFinite(weight)) throw new Error('LoRA 权重必须是有效数字');
    return { [prefix + 'lora_path']: path.trim(), [prefix + 'lora_weight']: weight };
}

export function LoraFields(props: { path: string; weight: number; label?: string;
    onPath: (path: string) => void; onWeight: (weight: number) => void }) {
    const label = props.label || 'LoRA';
    return <>
        <FormGroup label={`${label} 文件（可选）`} helperText="填写本地适配器权重文件路径，留空禁用">
            <InputGroup aria-label={`${label} 文件`} value={props.path}
                placeholder="models/lora/example.safetensors" onChange={e => props.onPath(e.target.value)} />
        </FormGroup>
        {props.path.trim() && <FormGroup label={`${label} 权重`}>
            <NumericInput aria-label={`${label} 权重`} fill stepSize={0.1} value={props.weight}
                onValueChange={props.onWeight} />
        </FormGroup>}
    </>;
}
