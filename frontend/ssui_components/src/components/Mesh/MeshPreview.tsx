import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

const MeshPreview = forwardRef((_props, ref) => {
    const [path, setPath] = useState('');
    const [error, setError] = useState(false);
    const viewer = useRef<HTMLElement>(null);
    useImperativeHandle(ref, () => ({
        onUpdate: (data: { path: string }) => { setError(false); setPath(data.path); }
    }), []);
    useEffect(() => {
        if (!path) return;
        let active = true;
        import('@google/model-viewer').catch(() => { if (active) setError(true); });
        const element = viewer.current;
        const failed = () => setError(true);
        element?.addEventListener('error', failed);
        return () => { active = false; element?.removeEventListener('error', failed); };
    }, [path]);
    if (!path) return <p>No 3D model</p>;
    const url = '/file?path=' + encodeURIComponent(path);
    return <div>
        {React.createElement('model-viewer', {
            key: path, ref: viewer, src: url, alt: 'Generated 3D model',
            'camera-controls': '', style: { width: '100%', height: '320px' }
        })}
        {error && <p>3D preview unavailable. The GLB can still be downloaded.</p>}
        <a href={url} download>Download GLB</a>
    </div>;
});

registerComponent({ name: 'MeshPreview', type: 'ssui.base.Mesh', port: 'output', component: MeshPreview } as ComponentRegister);
