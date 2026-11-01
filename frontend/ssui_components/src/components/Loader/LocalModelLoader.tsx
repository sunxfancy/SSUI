import React from 'react';
import { FormGroup, InputGroup } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

type Field = { key: string; label: string; optional?: boolean };
const folder: Field = { key: 'model_path', label: 'Model folder' };
const specs: { name: string; type: string; fields: Field[] }[] = [
    { name: 'Wan21ModelLoader', type: 'ssui_video.Wan21Resident.Wan21Model', fields: [folder] },
    { name: 'CogVideo2BModelLoader', type: 'ssui_video.CogVideo2B.CogVideo2BModel', fields: [folder] },
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
    class LocalModelLoader extends IComponent<{}, { values: Record<string, string> }> {
        state = { values: {} as Record<string, string> };
        onExecute() {
            const params: Record<string, string> = {};
            for (const field of spec.fields) {
                const value = this.state.values[field.key] || '';
                if (!value.trim() && !field.optional) throw new Error(`Select ${field.label.toLowerCase()}`);
                if (value.trim()) params[field.key] = value;
            }
            return { function: spec.type + '.load', params };
        }
        render() {
            return <div>{spec.fields.map(field => <FormGroup key={field.key} label={field.label}>
                <InputGroup aria-label={field.label} placeholder={field.label}
                    value={this.state.values[field.key] || ''}
                    onChange={event => this.setState({ values: { ...this.state.values, [field.key]: event.target.value } })} />
            </FormGroup>)}</div>;
        }
    }
    registerComponent({ name: spec.name, type: spec.type, port: 'input', component: LocalModelLoader } as ComponentRegister);
});
