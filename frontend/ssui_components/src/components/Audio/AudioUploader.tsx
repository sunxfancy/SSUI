import React, { useState, forwardRef, useImperativeHandle } from 'react';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

type AudioUploaderProps = {
    script_path: string;
}

const AudioUploader = forwardRef((props: AudioUploaderProps, ref) => {
    const [audio, setAudio] = useState<string>('');
    const [uploading, setUploading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useImperativeHandle(ref, () => {
        return {
            onExecute: () => {
                return { 'audio': audio };
            }
        }
    }, [audio]);

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
                setAudio(data.path);
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
        if (audio) {
            return <div>
                <audio controls src={'/file?path=' + audio}>
                    Your browser does not support the audio element.
                </audio>
            </div>
        }
    }

    return (
        <div>
            <h5>音频上传</h5>
            <input 
                type="file" 
                accept="audio/*"
                onChange={handleFileChange}
                disabled={uploading}
            />
            {uploading && <p>上传中...</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}
            {preview()}
        </div>
    );
});

const AudioPreview = forwardRef((props, ref) => {
    const [audio, setAudio] = useState<string>('');

    useImperativeHandle(ref, () => {
        return {
            onUpdate: (data: any) => {
                console.log('AudioPreview onUpdate:', data);
                setAudio(data.path);
            }
        }
    }, []);

    return (
        <div>
            {audio != '' ? 
                <audio 
                    controls 
                    src={'/file?path=' + audio}
                    style={{ 
                        width: '100%',
                        margin: '0 auto'
                    }}
                >
                    Your browser does not support the audio element.
                </audio> : 
                <p>No audio</p>
            }
        </div>
    );
});

// Register into the component manager
[
    { 'name': 'AudioUploader', 'type': 'ssui.base.Audio', 'port': 'input', 'component': AudioUploader } as ComponentRegister,
    { 'name': 'AudioPreview', 'type': 'ssui.base.Audio', 'port': 'output', 'component': AudioPreview } as ComponentRegister
].forEach(registerComponent);
