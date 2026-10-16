import React from 'react';
import { createPortal } from 'react-dom';
import { Button, HTMLSelect } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

type State = { files: string[]; path: string; image: string; draft: string; settings?: unknown; open: boolean; error: string; busy: boolean };

export class CanvasInput extends IComponent<{ script_path: string }, State> {
    state: State = { files: [], path: '', image: '', draft: '', open: false, error: '', busy: false };
    private frame = React.createRef<HTMLIFrameElement>();
    componentDidMount() { window.addEventListener('message', this.receive); this.refresh(); }
    componentWillUnmount() { window.removeEventListener('message', this.receive); }
    onExecute() { return { function: 'ssui.base.Image.load', params: { path: this.state.image } }; }
    private refresh = async () => {
        try {
            const response = await fetch('/files/canvas?' + new URLSearchParams({ script_path: this.props.script_path }));
            const files = await response.json();
            if (!response.ok || !Array.isArray(files)) throw new Error(files.error || '无法读取画布文件');
            this.setState({ files, error: '' });
        } catch (error) { this.setState({ error: String(error) }); }
    };
    private receive = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin || event.source !== this.frame.current?.contentWindow) return;
        if (event.data?.type === 'ssui-canvas-ready') {
            if (this.state.draft) this.frame.current?.contentWindow?.postMessage({ type: 'ssui-canvas-load', image: this.state.draft, settings: this.state.settings }, window.location.origin);
            return;
        }
        if (event.data?.type !== 'ssui-canvas-result' || typeof event.data.image !== 'string') return;
        this.setState({ busy: true, error: '' });
        try {
            const blob = await (await fetch(event.data.image)).blob();
            const body = new FormData();
            body.append('file', blob, `canvas-${crypto.randomUUID()}.png`);
            const response = await fetch('/files/upload?' + new URLSearchParams({ script_path: this.props.script_path }), { method: 'POST', body });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || '上传画布失败');
            this.setState({ image: data.path, draft: event.data.image, settings: event.data.settings, open: false });
        } catch (error) { this.setState({ error: String(error) }); }
        finally { this.setState({ busy: false }); }
    };
    render() {
        const params = new URLSearchParams({ path: this.state.path, input: '1' });
        return <div>
            <HTMLSelect value={this.state.path} onChange={e => this.setState({ path: e.target.value, draft: '', image: '', settings: undefined })}>
                <option value="">临时画布</option>
                {this.state.files.map(path => <option key={path} value={path}>{path}</option>)}
            </HTMLSelect>
            <Button icon="refresh" aria-label="刷新画布列表" onClick={this.refresh} />
            <Button icon="fullscreen" onClick={() => this.setState({ open: true, error: '' })}>放大画布 / 编辑输入</Button>
            {this.state.image && <img src={'/file?' + new URLSearchParams({ path: this.state.image })} alt="Canvas input" style={{ maxWidth: '100%', maxHeight: 200 }} />}
            {this.state.error && <p role="alert">{this.state.error}</p>}
            {this.state.open && createPortal(<div role="dialog" aria-modal="true" aria-label="画布输入" style={{ position: 'fixed', inset: 0, zIndex: 10000, background: '#fff' }}>
                <iframe ref={this.frame} title="Canvas editor" src={'/extension/ImageExtension/canvas/index.html?' + params} style={{ width: '100%', height: '100%', border: 0 }} />
                <div style={{ position: 'absolute', top: 8, left: '40%', background: '#fff', padding: 8 }}>
                    <Button disabled={this.state.busy} onClick={() => this.setState({ open: false })}>取消</Button>
                    <Button intent="primary" loading={this.state.busy} onClick={() => this.frame.current?.contentWindow?.postMessage({ type: 'ssui-canvas-export' }, window.location.origin)}>用作图片输入</Button>
                    {this.state.error && <p role="alert">{this.state.error}</p>}
                </div>
            </div>, document.body)}
        </div>;
    }
}
registerComponent({ name: 'CanvasInput', type: 'ssui.base.Image', port: 'input', component: CanvasInput } as ComponentRegister);
