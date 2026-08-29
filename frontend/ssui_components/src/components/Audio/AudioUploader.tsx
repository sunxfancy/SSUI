import React, { useState, forwardRef, useImperativeHandle } from 'react';
import { Callout, FileInput, NonIdealState, Spinner, Tag } from '@blueprintjs/core';
import { registerComponent, ComponentRegister } from '../ComponentsManager';
import '../Base/components.css';

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
                return { 'function': 'ssui.base.Audio.load', 'params': { 'path': audio } };
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
        <div className="component-media-editor">
            <FileInput fill text={audio ? audio.split(/[\\/]/).pop() : '选择音频文件'}
                inputProps={{ accept: 'audio/*' }} onInputChange={handleFileChange} disabled={uploading} />
            {uploading && <div className="component-media-status"><Spinner size={16} /> 正在上传…</div>}
            {error && <Callout compact intent="danger">{error}</Callout>}
            {preview()}
        </div>
    );
});

const AudioPreview = forwardRef((_props, ref) => {
    const [audio, setAudio] = useState<string>('');
    const [metadata, setMetadata] = useState<{ format?: string; sample_rate?: number; text?: string }>({});

    useImperativeHandle(ref, () => {
        return {
            onUpdate: (data: any) => {
                setAudio(data.path);
                setMetadata(data);
            }
        }
    }, []);

    return (
        <div>
            {audio != '' ? <div className="component-media-preview">
                <audio
                    controls
                    src={'/file?path=' + encodeURIComponent(audio)}
                >
                    Your browser does not support the audio element.
                </audio>
                <div className="component-media-meta">
                    {metadata.format && <Tag minimal>{metadata.format.toUpperCase()}</Tag>}
                    {metadata.sample_rate && <Tag minimal>{metadata.sample_rate} Hz</Tag>}
                </div>
                {metadata.text && <p>{metadata.text}</p>}
            </div> : <NonIdealState icon="music" title="等待音频结果" />
            }
        </div>
    );
});

// Register into the component manager
[
    { 'name': 'AudioUploader', 'type': 'ssui.base.Audio', 'port': 'input', 'component': AudioUploader } as ComponentRegister,
    { 'name': 'AudioPreview', 'type': 'ssui.base.Audio', 'port': 'output', 'component': AudioPreview } as ComponentRegister,
    { 'name': 'VoiceUploader', 'type': 'ssui.base.Voice', 'port': 'input', 'component': AudioUploader } as ComponentRegister,
    { 'name': 'VoicePreview', 'type': 'ssui.base.Voice', 'port': 'output', 'component': AudioPreview } as ComponentRegister
].forEach(registerComponent);
