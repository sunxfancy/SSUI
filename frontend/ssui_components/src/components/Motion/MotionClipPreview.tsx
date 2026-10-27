import React from 'react';
import { IComponent } from '../IComponent';
import { ComponentRegister, registerComponent } from '../ComponentsManager';
import './SkeletonPreview.css';

type Point = [number, number, number];
export type MotionData = { schema: string; fps: number; units: string; coordinate_system: string;
    joint_names: string[]; parents: number[]; positions: Point[][] };
type Payload = { path?: string; npz_path?: string; bvh_path?: string; model?: string };
type State = { payload?: Payload; data?: MotionData; index: number; yaw: number;
    playing: boolean; error?: string; loading: boolean; followRoot: boolean; zoom: number };

export function validateMotion(data: MotionData): MotionData {
    if (data.schema !== 'ssui.motion.clip/v1' || !(data.fps > 0 && data.fps <= 240)
        || !data.joint_names?.length || data.parents?.length !== data.joint_names.length
        || !data.positions?.length || data.units !== 'meters' || data.coordinate_system !== 'Y-up;+Z-forward') {
        throw new Error('无法识别的 3D 动作数据。');
    }
    data.parents.forEach((parent, i) => {
        if (!Number.isInteger(parent) || parent < -1 || parent >= i) throw new Error('骨骼层级无效。');
    });
    for (const frame of data.positions) {
        if (frame.length !== data.parents.length || frame.some(point => point.length !== 3 || !point.every(Number.isFinite))) {
            throw new Error('动作包含无效的关节坐标。');
        }
    }
    return data;
}

export function projectPoint(point: Point, center: Point, radius: number, yaw: number): [number, number] {
    const a = yaw * Math.PI / 180;
    const [x, y, z] = point.map((value, i) => value - center[i]);
    const horizontal = Math.cos(a) * x + Math.sin(a) * z;
    const depth = -Math.sin(a) * x + Math.cos(a) * z;
    return [200 + horizontal / radius * 130, 160 - (Math.cos(.3) * y - Math.sin(.3) * depth) / radius * 130];
}

export class MotionClipPreview extends IComponent<{}, State> {
    state: State = { index: 0, yaw: 35, playing: false, loading: false, followRoot: true, zoom: 1 };
    private timer?: ReturnType<typeof setInterval>;
    private request?: AbortController;
    private center: Point = [0, 0, 0];
    private radius = 1;
    private bodyCenter: Point = [0, 0, 0];
    private bodyRadius = 1;

    private stop() {
        if (this.timer) clearInterval(this.timer);
        this.timer = undefined;
    }

    override componentWillUnmount() { this.stop(); this.request?.abort(); }

    override async onUpdate(payload: Payload) {
        this.stop(); this.request?.abort();
        this.setState({ payload, data: undefined, index: 0, playing: false, loading: true, error: undefined });
        const request = new AbortController();
        this.request = request;
        try {
            if (!payload.path) throw new Error('没有动作预览文件。');
            const response = await fetch('/file?path=' + encodeURIComponent(payload.path), { signal: request.signal });
            if (!response.ok) throw new Error(`读取动作失败 (${response.status})`);
            const data = validateMotion(await response.json());
            if (request.signal.aborted) return;
            const low: Point = [Infinity, Infinity, Infinity], high: Point = [-Infinity, -Infinity, -Infinity];
            for (const frame of data.positions) for (const p of frame) for (let axis = 0; axis < 3; axis++) {
                low[axis] = Math.min(low[axis], p[axis]); high[axis] = Math.max(high[axis], p[axis]);
            }
            this.center = low.map((value, i) => (value + high[i]) / 2) as Point;
            this.radius = Math.max(.1, Math.hypot(...high.map((value, i) => (value - low[i]) / 2)));
            const root = data.parents.indexOf(-1);
            const bodyLow: Point = [Infinity, Infinity, Infinity], bodyHigh: Point = [-Infinity, -Infinity, -Infinity];
            for (const frame of data.positions) for (const p of frame) for (let axis = 0; axis < 3; axis++) {
                const value = p[axis] - frame[root][axis];
                bodyLow[axis] = Math.min(bodyLow[axis], value); bodyHigh[axis] = Math.max(bodyHigh[axis], value);
            }
            this.bodyCenter = bodyLow.map((value, i) => (value + bodyHigh[i]) / 2) as Point;
            this.bodyRadius = Math.max(.1, Math.hypot(...bodyHigh.map((value, i) => (value - bodyLow[i]) / 2)));
            this.setState({ data, loading: false });
        } catch (error) {
            if (!request.signal.aborted) this.setState({ loading: false, error: String(error) });
        }
    }

    togglePlayback = () => {
        if (this.state.playing) { this.stop(); this.setState({ playing: false }); return; }
        const data = this.state.data;
        if (!data) return;
        this.setState({ playing: true });
        this.timer = setInterval(() => this.setState(state => ({ index: (state.index + 1) % data.positions.length })), 1000 / data.fps);
    };

    override render() {
        const { data, index, yaw, playing, loading, error, payload, followRoot, zoom } = this.state;
        const frame = data?.positions[index];
        const root = frame?.[data!.parents.indexOf(-1)];
        const center = followRoot && root ? this.bodyCenter.map((value, i) => value + root[i]) as Point : this.center;
        const radius = (followRoot ? this.bodyRadius : this.radius) / zoom;
        const points = frame?.map(point => projectPoint(point, center, radius, yaw)) ?? [];
        return <section className="motion-inspector">
            <header className="motion-header"><strong>3D 动作 · {payload?.model || 'Kimodo'}</strong></header>
            {loading && <p>正在载入动作…</p>}
            {error && <p role="alert">{error}</p>}
            {!data && !loading && !error && <p>运行工作流后可播放生成的骨骼动画。</p>}
            {data && <>
                <svg viewBox="0 0 400 320" role="img" aria-label="生成的 3D 骨骼动作" style={{ width: '100%', background: '#101923' }}>
                    {data.parents.map((parent, i) => parent >= 0 && <line key={`bone-${i}`} x1={points[parent][0]} y1={points[parent][1]}
                        x2={points[i][0]} y2={points[i][1]} stroke="#53d8e8" strokeWidth="2" />)}
                    {points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="2" fill="#ffcc77" />)}
                </svg>
                <div><button type="button" onClick={this.togglePlayback}>{playing ? '暂停' : '播放'}</button>
                    <span> {index + 1} / {data.positions.length} 帧 · {data.fps} FPS · {(data.positions.length / data.fps).toFixed(1)} 秒</span></div>
                <label>帧 <input type="range" aria-label="动作帧" min="0" max={data.positions.length - 1} value={index}
                    onChange={event => this.setState({ index: Number(event.target.value) })} /></label>
                <label>视角 <input type="range" aria-label="3D 视角" min="-180" max="180" value={yaw}
                    onChange={event => this.setState({ yaw: Number(event.target.value) })} /></label>
                <label>缩放 <input type="range" aria-label="预览缩放" min="0.5" max="3" step="0.1" value={zoom}
                    onChange={event => this.setState({ zoom: Number(event.target.value) })} /></label>
                <label><input type="checkbox" checked={followRoot}
                    onChange={event => this.setState({ followRoot: event.target.checked })} />跟随角色</label>
            </>}
            <nav aria-label="动作文件下载">{([['NPZ', payload?.npz_path], ['BVH', payload?.bvh_path], ['JSON', payload?.path]] as const)
                .map(([name, path]) => path && <a key={name} href={'/file?path=' + encodeURIComponent(path)} download style={{ marginRight: 12 }}>下载 {name}</a>)}</nav>
        </section>;
    }
}

registerComponent({ name: 'MotionClipPreview', type: 'ssui.base.MotionClip', port: 'output', component: MotionClipPreview } as ComponentRegister);
