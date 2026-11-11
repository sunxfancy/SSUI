import { LoraFields, loraParams } from './LoraFields';
import React from 'react';
import { FormGroup, InputGroup } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

type Field = { key: string; label: string; optional?: boolean };
const folder: Field = { key: 'model_path', label: 'Model folder' };
const specs: { name: string; type: string; fields: Field[]; lora?: boolean; dual?: boolean; method?: string }[] = [
    { name: 'WanVideoModelLoader', type: 'ssui_video.Wan.WanVideoModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'Wan2T2VModelLoader', type: 'ssui_video.Wan2.Wan2T2VModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'Wan2I2VModelLoader', type: 'ssui_video.Wan2.Wan2I2VModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'Wan21T2V13BModelLoader', type: 'ssui_video.Wan21.Wan21T2V13BModel', fields: [{ key: 'model_dir', label: 'Wan model folder (optional)', optional: true }], lora: true, dual: false, method: 'load_local' },
    { name: 'Wan22TI2VModelLoader', type: 'ssui_video.Wan22.Wan22TI2VModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'Wan22T2VA14BModelLoader', type: 'ssui_video.Wan22.Wan22T2VA14BModel', fields: [], lora: true, dual: true, method: 'load' },
    { name: 'Wan22I2VA14BModelLoader', type: 'ssui_video.Wan22.Wan22I2VA14BModel', fields: [], lora: true, dual: true, method: 'load' },
    { name: 'CogVideoModelLoader', type: 'ssui_video.CogVideo.CogVideoModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'HunyuanVideoModelLoader', type: 'ssui_video.Hunyuan.HunyuanVideoModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'HunyuanImageToVideoModelLoader', type: 'ssui_video.Hunyuan.HunyuanImageToVideoModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'AnimateDiffModelLoader', type: 'ssui_video.AnimateDiff.AnimateDiffModel', fields: [], lora: true, dual: false, method: 'load' },
    { name: 'Wan21ModelLoader', type: 'ssui_video.Wan21Resident.Wan21Model', fields: [folder], lora: true },
    { name: 'CogVideo2BModelLoader', type: 'ssui_video.CogVideo2B.CogVideo2BModel', fields: [folder], lora: true },
    { name: 'ShapEModelLoader', type: 'ssui_3dmodel.ShapE.ShapEModel', fields: [folder] },
    { name: 'TrellisModelLoader', type: 'ssui_3dmodel.Trellis.TrellisModel', fields: [folder,
        { key: 'dinov2_repository', label: 'DINOv2 source folder (offline, optional)', optional: true },
        { key: 'dinov2_weights', label: 'DINOv2 weights (offline, optional)', optional: true }] },
    { name: 'MDMModelLoader', type: 'ssui_motion.MDM.MDMModel', fields: [
        { key: 'repository_path', label: 'MDM source folder' },
        { key: 'checkpoint_path', label: 'MDM checkpoint file' },
        { key: 'python_path', label: 'Python executable (optional)', optional: true }] },
];

specs.forEach(spec => {
    class LocalModelLoader extends IComponent<{}, { values: Record<string, string>; loraPath: string; loraWeight: number; lowPath: string; lowWeight: number }> {
        protected persistedFields: ('values' | 'loraPath' | 'loraWeight' | 'lowPath' | 'lowWeight')[] = ['values', 'loraPath', 'loraWeight', 'lowPath', 'lowWeight'];
        state = { values: {} as Record<string, string>, loraPath: '', loraWeight: 1, lowPath: '', lowWeight: 1 };
        onExecute() {
            const params: Record<string, string | number> = {};
            for (const field of spec.fields) {
                const value = this.state.values[field.key] || '';
                if (!value.trim() && !field.optional) throw new Error(`Select ${field.label.toLowerCase()}`);
                if (value.trim()) params[field.key] = value;
            }
            if (spec.lora) Object.assign(params, loraParams(this.state.loraPath, this.state.loraWeight, spec.dual ? 'high_noise_' : ''));
            if (spec.dual) Object.assign(params, loraParams(this.state.lowPath, this.state.lowWeight, 'low_noise_'));
            return { function: spec.type + '.' + (spec.method || 'load'), params };
        }
        render() {
            return <div>{spec.fields.map(field => <FormGroup key={field.key} label={field.label}>
                <InputGroup aria-label={field.label} placeholder={field.label}
                    value={this.state.values[field.key] || ''}
                    onChange={event => this.setState({ values: { ...this.state.values, [field.key]: event.target.value } })} />
            </FormGroup>)}
                {spec.lora && <LoraFields path={this.state.loraPath} weight={this.state.loraWeight}
                    label={spec.dual ? '高噪声 LoRA' : 'LoRA'}
                    onPath={loraPath => this.setState({ loraPath })} onWeight={loraWeight => this.setState({ loraWeight })} />}
                {spec.dual && <LoraFields path={this.state.lowPath} weight={this.state.lowWeight} label="低噪声 LoRA"
                    onPath={lowPath => this.setState({ lowPath })} onWeight={lowWeight => this.setState({ lowWeight })} />}
            </div>;
        }
    }
    registerComponent({ name: spec.name, type: spec.type, port: 'input', component: LocalModelLoader } as ComponentRegister);
});
