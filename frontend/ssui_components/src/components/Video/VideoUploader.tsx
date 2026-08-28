import React, { useState, forwardRef, useImperativeHandle } from 'react';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

type VideoUploaderProps = {
    script_path: string;
}

const VideoUploader = forwardRef((props: VideoUploaderProps, ref) => {
    const [video, setVideo] = useState<string>('');
    const [uploading, setUploading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useImperativeHandle(ref, () => {
        return {
            onExecute: () => {
                return { 'video': video };
            }
        }
    }, [video]);

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
                <video src={'/file?path=' + encodeURIComponent(video)} controls muted style={{ maxWidth: '100%', height: 'auto' }} />
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
    const [video, setVideo] = useState<string>('');
    const [metadata, setMetadata] = useState<Record<string, string | number | null>>({});

    useImperativeHandle(ref, () => {
        return {
            onUpdate: (data: any) => {
                console.log('VideoPreview onUpdate:', data);
                setVideo(data.path);
                setMetadata(data.metadata || {});
            }
        }
    }, []);

    return (
        <div>
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
