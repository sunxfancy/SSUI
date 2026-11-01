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
                <video controls playsInline src={'/file?path=' + encodeURIComponent(video)} style={{ maxWidth: '100%', height: 'auto' }} />
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
    const [artifacts, setArtifacts] = useState<{ name: string; path: string }[]>([]);

    useImperativeHandle(ref, () => {
        return {
            onUpdate: (data: any) => {
                console.log('VideoPreview onUpdate:', data);
                setVideo(data.path);
                setArtifacts(data.artifacts || []);
            }
        }
    }, []);

    return (
        <div>
            {video != '' ?
                <video controls playsInline
                    src={'/file?path=' + encodeURIComponent(video)}
                    style={{
                        maxWidth: '100%',
                        height: 'auto',
                        display: 'block',
                        margin: '0 auto'
                    }}
                /> :
                <p>No video</p>
            }
            {artifacts.map(file => <a key={file.path} href={'/file?path=' + encodeURIComponent(file.path)} download={file.name}>{file.name}</a>)}
        </div>
    );
});

// Register into the component manager
[
    { 'name': 'VideoUploader', 'type': 'ssui.base.Video', 'port': 'input', 'component': VideoUploader } as ComponentRegister,
    { 'name': 'VideoPreview', 'type': 'ssui.base.Video', 'port': 'output', 'component': VideoPreview } as ComponentRegister
].forEach(registerComponent);
