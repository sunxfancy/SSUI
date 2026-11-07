import { useUIState } from '../../UIState';
import React, { useState, forwardRef, useImperativeHandle } from 'react';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

type VideoUploaderProps = {
    script_path: string;
}

const VideoUploader = forwardRef((props: VideoUploaderProps, ref) => {
    const [video, setVideo] = useUIState<string>('video', '');
    const [anchor, setAnchor] = useUIState<{ x: number; y: number } | null>('anchor', null);
    const [uploading, setUploading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useImperativeHandle(ref, () => {
        return {
            onExecute: () => {
                return { 'video': video, 'metadata': anchor ? { anchor_x: anchor.x, anchor_y: anchor.y } : {} };
            }
        }
    }, [video, anchor]);

    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setUploading(true);
        setError(null);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`/files/upload?script_path=${props.script_path}`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                setVideo(data.path);
                setAnchor(null);
                setUploading(false);
            } else {
                setError(data.error || '上传失败');
                setUploading(false);
            }
        } catch (error) {
            setError('上传过程中发生错误');
            setUploading(false);
            console.error('上传错误:', error);
        }
    };

    const preview = () => {
        if (video) {
            return <div>
                <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%' }}>
                    <video src={'/file?path=' + encodeURIComponent(video)} controls muted onClick={event => {
                        if (event.currentTarget.currentTime > 0.1) {
                            setError('请先将视频移到开头，再点击首帧中的锚点。');
                            return;
                        }
                        const bounds = event.currentTarget.getBoundingClientRect();
                        setAnchor({ x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height });
                        setError(null);
                    }} style={{ maxWidth: '100%', height: 'auto', display: 'block', cursor: 'crosshair' }} />
                    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                        {anchor && <span style={{ position: 'absolute', left: `${anchor.x * 100}%`, top: `${anchor.y * 100}%`, color: '#ff4d4d', fontSize: 26, transform: 'translate(-50%, -50%)', pointerEvents: 'none' }}>⊕</span>}
                    </div>
                </div>
                <div style={{ fontSize: 12 }}>在首帧点击 3D 锚点；留空则使用文本位置建议。</div>
                {anchor && <button type="button" onClick={() => setAnchor(null)}>使用自动建议</button>}
            </div>
        }
    }

    return (
        <div>
            <h5>视频上传</h5>
            <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                disabled={uploading}
            />
            {uploading && <p>上传中...</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}
            {preview()}
        </div>
    );
});

const VideoPreview = forwardRef((props, ref) => {
    const [video, setVideo] = useUIState<string>('video', '');
    const [artifacts, setArtifacts] = useUIState<{name: string; path: string}[]>('artifacts', []);
    const [metadata, setMetadata] = useUIState<Record<string, string | number | null>>('metadata', {});

    useImperativeHandle(ref, () => {
        return {
            onUpdate: (data: any) => {
                console.log('VideoPreview onUpdate:', data);
                setVideo(data.path);
                setMetadata(data.metadata || {});
                setArtifacts(data.artifacts || []);
            }
        }
    }, []);

    return (
        <div>
            {artifacts.map(item => <a key={item.path} href={'/file?path=' + encodeURIComponent(item.path)} download>{item.name}</a>)}
            {video != '' ? <>
                <video
                    src={'/file?path=' + encodeURIComponent(video)}
                    controls
                    muted
                    style={{
                        maxWidth: '100%',
                        height: 'auto',
                        display: 'block',
                        margin: '0 auto'
                    }}
                />
                {typeof metadata.anchor_confidence === 'number' && <div style={{ marginTop: 8, fontSize: 12 }}>
                    锚点：{metadata.anchor_source === 'manual' ? '手动指定' : metadata.anchor_source === 'vision_grounder' ? '视觉模型建议' : '文本方位建议'}
                    {' · 置信度 '}{Math.round(metadata.anchor_confidence * 100)}%
                    {metadata.anchor_confidence < 0.5 && ' · 建议在上传视频的首帧点击确认位置'}
                </div>}
                {metadata.kind === 'blender_scene_composite' && <div style={{ marginTop: 8, fontSize: 12 }}>
                    Blender {metadata.blender_version || 'unknown'}
                    {typeof metadata.solve_error_px === 'number' && ` · 解算重投影误差 ${metadata.solve_error_px.toFixed(2)} px`}
                    {typeof metadata.camera_frames === 'number' && ` · ${metadata.camera_frames} 帧相机轨迹`}
                    <div style={{ marginTop: 4 }}>
                        {(['scene_path', 'report_path'] as const).map(key => {
                            const path = metadata[key];
                            if (typeof path !== 'string' || !path) return null;
                            return <a key={key} href={'/file?path=' + encodeURIComponent(path)} download style={{ marginRight: 10 }}>
                                {key === 'scene_path' ? '下载 Blender 工程' : '下载解算报告'}
                            </a>;
                        })}
                    </div>
                </div>}
                {metadata.kind === 'blender_comparison' && <div style={{ marginTop: 8, fontSize: 12 }}>
                    <div>
                        Blender {metadata.blender_version || 'unknown'}
                        {typeof metadata.comparison_rmse === 'number' && ` · RMSE ${metadata.comparison_rmse.toFixed(6)}`}
                    </div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
                        {['scene_path', 'report_path', 'bvh_path', 'retarget_path'].map(key => {
                            const path = metadata[key];
                            if (typeof path !== 'string' || !path) return null;
                            const labels: Record<string, string> = {
                                scene_path: 'BLEND', report_path: '报告', bvh_path: 'BVH', retarget_path: '重定向',
                            };
                            return <a key={key} href={'/file?path=' + encodeURIComponent(path)} download>{labels[key]}</a>;
                        })}
                    </div>
                </div>}
            </> :
                <p>No video</p>
            }
        </div>
    );
});

// Register into the component manager
[
    { 'name': 'VideoUploader', 'type': 'ssui.base.Video', 'port': 'input', 'component': VideoUploader } as ComponentRegister,
    { 'name': 'VideoPreview', 'type': 'ssui.base.Video', 'port': 'output', 'component': VideoPreview } as ComponentRegister
].forEach(registerComponent);
