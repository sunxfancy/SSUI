import React from 'react';
import { Checkbox, FormGroup, InputGroup, NumericInput, Tag, TextArea } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { ComponentRegister, registerComponent } from '../ComponentsManager';
import './components.css';

type Scalar = string | number | boolean | null;

class StringEditor extends IComponent<{}, { value: string }> {
    state = { value: '' };
    override onExecute() { return this.state.value; }
    override render() {
        return <InputGroup fill value={this.state.value} placeholder="输入文本" onChange={event => this.setState({ value: event.target.value })} />;
    }
}

class NumberEditor extends IComponent<{ integer?: boolean }, { value: number }> {
    state = { value: 0 };
    override onExecute() { return this.props.integer ? Math.trunc(this.state.value) : this.state.value; }
    override render() {
        return <NumericInput fill value={this.state.value} minorStepSize={this.props.integer ? null : 0.1}
            stepSize={this.props.integer ? 1 : 0.1} onValueChange={value => this.setState({ value })} />;
    }
}

class IntegerEditor extends NumberEditor {
    override onExecute() { return Math.trunc(this.state.value); }
    override render() {
        return <NumericInput fill value={this.state.value} minorStepSize={null} stepSize={1}
            onValueChange={value => this.setState({ value })} />;
    }
}

class BooleanEditor extends IComponent<{}, { value: boolean }> {
    state = { value: false };
    override onExecute() { return this.state.value; }
    override render() {
        return <Checkbox checked={this.state.value} label={this.state.value ? '已启用' : '未启用'}
            onChange={event => this.setState({ value: event.currentTarget.checked })} />;
    }
}

class ScalarPreview extends IComponent<{}, { value: Scalar }> {
    state: { value: Scalar } = { value: null };
    override onUpdate(value: Scalar) { this.setState({ value }); }
    override render() {
        return <div className="component-scalar-preview">
            <Tag minimal>{typeof this.state.value}</Tag>
            <code>{this.state.value === null ? '等待运行结果' : String(this.state.value)}</code>
        </div>;
    }
}

class JsonEditor extends IComponent<{ type: string }, { value: string; error?: string }> {
    state = { value: '', error: undefined as string | undefined };
    override onExecute() {
        if (!this.state.value.trim()) return null;
        try {
            const value = JSON.parse(this.state.value);
            this.setState({ error: undefined });
            return value;
        } catch {
            this.setState({ error: '请输入有效的 JSON。' });
            return null;
        }
    }
    override render() {
        return <FormGroup helperText={this.state.error ?? `未找到 ${this.props.type} 的专用组件，使用 JSON 传入原始值。`}
            intent={this.state.error ? 'danger' : 'none'}>
            <TextArea fill rows={5} value={this.state.value} placeholder="{}"
                onChange={event => this.setState({ value: event.target.value, error: undefined })} />
        </FormGroup>;
    }
}

class JsonPreview extends IComponent<{ type: string }, { value: unknown }> {
    state: { value: unknown } = { value: undefined };
    override onUpdate(value: unknown) { this.setState({ value }); }
    override render() {
        return <div className="component-json-preview">
            <div><Tag minimal icon="code">{this.props.type}</Tag></div>
            <pre>{this.state.value === undefined ? '等待运行结果' : JSON.stringify(this.state.value, null, 2)}</pre>
        </div>;
    }
}

const registrations: ComponentRegister[] = [
    { name: 'StringEditor', type: 'builtins.str', port: 'input', component: StringEditor } as ComponentRegister,
    { name: 'StringPreview', type: 'builtins.str', port: 'output', component: ScalarPreview } as ComponentRegister,
    { name: 'IntegerEditor', type: 'builtins.int', port: 'input', component: IntegerEditor } as ComponentRegister,
    { name: 'IntegerPreview', type: 'builtins.int', port: 'output', component: ScalarPreview } as ComponentRegister,
    { name: 'FloatEditor', type: 'builtins.float', port: 'input', component: NumberEditor } as ComponentRegister,
    { name: 'FloatPreview', type: 'builtins.float', port: 'output', component: ScalarPreview } as ComponentRegister,
    { name: 'BooleanEditor', type: 'builtins.bool', port: 'input', component: BooleanEditor } as ComponentRegister,
    { name: 'BooleanPreview', type: 'builtins.bool', port: 'output', component: ScalarPreview } as ComponentRegister,
    { name: 'JsonEditor', type: '*', port: 'input', component: JsonEditor } as ComponentRegister,
    { name: 'JsonPreview', type: '*', port: 'output', component: JsonPreview } as ComponentRegister,
];

registrations.forEach(registerComponent);

export { BooleanEditor, IntegerEditor, JsonEditor, JsonPreview, NumberEditor, ScalarPreview, StringEditor };
