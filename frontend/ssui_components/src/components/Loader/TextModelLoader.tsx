import React from 'react';
import { Checkbox, FormGroup, HTMLSelect, InputGroup, NumericInput } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { registerComponent } from '../ComponentsManager';

let nextId = 0;
interface State { modelPath: string; loraPath: string; weight: number; device: string; localOnly: boolean; }

export class TextModelLoader extends IComponent<{ legacy?: boolean }, State> {
    private id = `text-model-${++nextId}`;
    protected persistedFields: (keyof State)[] = ['modelPath', 'loraPath', 'weight', 'device', 'localOnly'];
    state: State = { modelPath: '', loraPath: '', weight: 1, device: 'auto', localOnly: false };

    onExecute() {
        if (!this.state.modelPath.trim()) throw new Error('请先填写文本模型目录或模型 ID');
        if (this.props.legacy) return { function: 'ssui_llm.Qwen.QwenModel.load', params: { model_path: this.state.modelPath.trim() } };
        if (!Number.isFinite(this.state.weight)) throw new Error('LoRA 权重必须是有效数字');
        return {
            function: 'ssui_llm.Text.TextModel.load',
            params: { model_path: this.state.modelPath.trim(), lora_path: this.state.loraPath.trim(),
                lora_weight: this.state.weight, device: this.state.device, local_files_only: this.state.localOnly },
        };
    }

    render() {
        return <div className="workflow-loader">
            <FormGroup label="文本模型" labelFor={`${this.id}-model`} helperText="本地模型目录或 Hugging Face 模型 ID">
                <InputGroup id={`${this.id}-model`} value={this.state.modelPath} placeholder="D:/Models/my-text-model"
                    onChange={event => this.setState({ modelPath: event.target.value })} />
            </FormGroup>
            {!this.props.legacy && <>
                <FormGroup label="LoRA（可选）" labelFor={`${this.id}-lora`} helperText="PEFT 适配器目录或模型 ID">
                    <InputGroup id={`${this.id}-lora`} value={this.state.loraPath} placeholder="不使用 LoRA 时留空"
                        onChange={event => this.setState({ loraPath: event.target.value })} />
                </FormGroup>
                {this.state.loraPath.trim() && <FormGroup label="LoRA 权重" labelFor={`${this.id}-weight`}>
                    <NumericInput id={`${this.id}-weight`} fill stepSize={0.1} value={this.state.weight}
                        onValueChange={weight => this.setState({ weight })} />
                </FormGroup>}
                <FormGroup label="运行设备" labelFor={`${this.id}-device`}>
                    <HTMLSelect id={`${this.id}-device`} fill value={this.state.device} onChange={event => this.setState({ device: event.target.value })}
                        options={[{ label: '自动选择', value: 'auto' }, { label: 'CPU', value: 'cpu' },
                            { label: 'CUDA / ROCm', value: 'cuda' }, { label: 'Apple MPS', value: 'mps' }]} />
                </FormGroup>
                <Checkbox checked={this.state.localOnly} label="仅使用本地文件" onChange={event => this.setState({ localOnly: event.currentTarget.checked })} />
            </>}
        </div>;
    }
}

registerComponent({ name: '文本模型', type: 'ssui_llm.Text.TextModel', port: 'input', component: TextModelLoader,
    createComponent: (ref, props) => <TextModelLoader {...props} ref={ref as unknown as React.RefObject<TextModelLoader>} /> });
registerComponent({ name: 'Qwen 模型', type: 'ssui_llm.Qwen.QwenModel', port: 'input', component: TextModelLoader,
    createComponent: (ref, props) => <TextModelLoader {...props} legacy ref={ref as unknown as React.RefObject<TextModelLoader>} /> });
