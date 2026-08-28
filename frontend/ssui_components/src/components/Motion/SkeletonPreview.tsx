import React from 'react';
import { registerComponent, ComponentRegister } from '../ComponentsManager';
import { IComponent } from '../IComponent';
import './SkeletonPreview.css';

type Landmark = { name: string; x: number; y: number; z: number; visibility: number };
type PoseFrame = { frame_index: number; timestamp: number; landmarks: Landmark[]; detected: boolean };
type AnimationData = { frames: PoseFrame[]; fps: number; width: number; height: number; model: string };
type State = { data?: AnimationData; index: number; loading: boolean; error?: string; path?: string; bvhPath?: string; retargetPath?: string; retargetRmse?: number };

const connections = [
    [0,2],[2,5],[5,0],[2,7],[5,8],[11,12],[11,13],[13,15],[12,14],[14,16],
    [11,23],[12,24],[23,24],[23,25],[25,27],[27,31],[24,26],[26,28],[28,32],
];

export class SkeletonPreview extends IComponent<{}, State> {
    state: State = { index: 0, loading: false };

    override async onUpdate(payload: { path?: string; bvh_path?: string; retarget_path?: string; retarget_rmse?: number }): Promise<void> {
        if (!payload?.path) {
            this.setState({ error: '识别结果没有数据文件。' });
            return;
        }
        this.setState({ loading: true, error: undefined, path: payload.path, bvhPath: payload.bvh_path, retargetPath: payload.retarget_path, retargetRmse: payload.retarget_rmse });
        try {
            const response = await fetch('/file?path=' + encodeURIComponent(payload.path));
            if (!response.ok) throw new Error(`读取失败 (${response.status})`);
            const data = await response.json() as AnimationData;
            this.setState({ data, index: 0, loading: false });
        } catch (error) {
            this.setState({ loading: false, error: error instanceof Error ? error.message : '无法读取骨骼数据。' });
        }
    }

    private renderSkeleton(frame?: PoseFrame) {
        const points = frame?.landmarks ?? [];
        return (
            <svg className="skeleton-stage" viewBox="0 0 100 100" role="img" aria-label="当前帧骨骼">
                <defs><filter id="joint-glow"><feGaussianBlur stdDeviation="0.75" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
                {connections.map(([a,b], i) => points[a] && points[b] && Math.min(points[a].visibility, points[b].visibility) > .3 ?
                    <line key={i} x1={points[a].x*100} y1={points[a].y*100} x2={points[b].x*100} y2={points[b].y*100} className="skeleton-bone"/> : null)}
                {points.map((point, i) => point.visibility > .3 ?
                    <circle key={i} cx={point.x*100} cy={point.y*100} r="1.05" className="skeleton-joint"/> : null)}
            </svg>
        );
    }

    override render() {
        const { data, index, loading, error, path, bvhPath, retargetPath, retargetRmse } = this.state;
        const frame = data?.frames[index];
        return <section className="motion-inspector">
            <header className="motion-header">
                <div><span className="motion-kicker">MOTION / POSE 33</span><strong>骨骼动画</strong></div>
                {data && <span className={frame?.detected ? 'tracking live' : 'tracking'}>{frame?.detected ? '已锁定' : '推算帧'}</span>}
            </header>
            {loading && <div className="motion-empty">正在载入动作轨迹…</div>}
            {error && <div className="motion-error">{error}</div>}
            {!loading && !error && !data && <div className="motion-empty">运行骨骼识别后，在这里逐帧检查动作。</div>}
            {data && <>
                <div className="stage-shell">{this.renderSkeleton(frame)}<span className="frame-stamp">{frame?.timestamp.toFixed(2)}s</span></div>
                <input className="motion-timeline" aria-label="动画帧" type="range" min="0" max={Math.max(0, data.frames.length-1)} value={index}
                    onChange={event => this.setState({ index: Number(event.target.value) })}/>
                <footer className="motion-meta">
                    <span>{index + 1} / {data.frames.length} 帧</span><span>{data.fps.toFixed(1)} FPS</span>
                    {typeof retargetRmse === 'number' && <span title="固定骨长 BVH 与识别关键点之间的均方根误差">误差 {retargetRmse.toFixed(3)}</span>}
                    <span className="motion-exports">
                        {path && <a href={'/file?path=' + encodeURIComponent(path)} download>JSON</a>}
                        {bvhPath && <a href={'/file?path=' + encodeURIComponent(bvhPath)} download>BVH</a>}
                        {retargetPath && <a href={'/file?path=' + encodeURIComponent(retargetPath)} download>报告</a>}
                    </span>
                </footer>
            </>}
        </section>;
    }
}

registerComponent({
    name: 'SkeletonPreview', type: 'ssui.base.SkeletonAnimation', port: 'output', component: SkeletonPreview,
} as ComponentRegister);
