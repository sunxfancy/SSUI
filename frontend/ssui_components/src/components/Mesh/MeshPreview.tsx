import React, { useEffect, useRef, useState } from 'react';

type Part = { name: string; vertices: number[][]; faces: number[][] };

/** Local canvas preview; quad edges come from the polygon master, not GLB. */
export function MeshPreview({ path }: { path: string }) {
    const canvas = useRef<HTMLCanvasElement>(null);
    const [parts, setParts] = useState<Part[]>([]);
    const [error, setError] = useState('');
    const [selected, setSelected] = useState(-1);
    const [angle, setAngle] = useState([0.35, 0.4]);
    const [zoom, setZoom] = useState(1);
    const drag = useRef<number[] | null>(null);
    useEffect(() => {
        const abort = new AbortController();
        fetch('/file?path=' + encodeURIComponent(path), { signal: abort.signal })
            .then(response => { if (!response.ok) throw new Error('预览加载失败'); return response.json(); })
            .then(setParts).catch(e => { if (e.name !== 'AbortError') setError(String(e)); });
        return () => abort.abort();
    }, [path]);
    useEffect(() => {
        const ctx = canvas.current?.getContext('2d');
        if (!ctx) return;
        ctx.fillStyle = '#151b28'; ctx.fillRect(0, 0, 640, 360);
        const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
        for (const part of parts) for (const v of part.vertices) for (let i = 0; i < 3; i++) {
            min[i] = Math.min(min[i], v[i]); max[i] = Math.max(max[i], v[i]);
        }
        const center = min.map((v, i) => (v + max[i]) / 2);
        const scale = 270 * zoom / (Math.max(...max.map((v, i) => v - min[i])) || 1);
        const [yaw, pitch] = angle;
        const polygons: { points: number[][]; depth: number; color: string }[] = [];
        parts.forEach((part, index) => {
            if (selected >= 0 && selected !== index) return;
            const vertices = part.vertices.map(v => {
                const [x, y, z] = v.map((n, i) => n - center[i]);
                const rx = x * Math.cos(yaw) + z * Math.sin(yaw);
                const rz = -x * Math.sin(yaw) + z * Math.cos(yaw);
                return [320 + rx * scale, 180 - (y * Math.cos(pitch) - rz * Math.sin(pitch)) * scale,
                    y * Math.sin(pitch) + rz * Math.cos(pitch)];
            });
            const step = Math.max(1, Math.ceil(part.faces.length / 20000));
            for (let f = 0; f < part.faces.length; f += step) {
                const points = part.faces[f].map(i => vertices[i]);
                polygons.push({ points, depth: points.reduce((sum, p) => sum + p[2], 0) / points.length,
                    color: `hsl(${index * 137.5 % 360}, 48%, 60%)` });
            }
        });
        polygons.sort((a, b) => a.depth - b.depth).forEach(({ points, color }) => {
            ctx.beginPath(); points.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
            ctx.closePath(); ctx.fillStyle = color; ctx.fill(); ctx.strokeStyle = '#243042'; ctx.lineWidth = 0.5; ctx.stroke();
        });
    }, [parts, selected, angle, zoom]);
    return <div className="mesh-preview">
        <canvas ref={canvas} width={640} height={360} aria-label="3D 模型预览，拖动旋转"
            onPointerDown={e => { drag.current = [e.clientX, e.clientY]; e.currentTarget.setPointerCapture(e.pointerId); }}
            onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}
            onPointerMove={e => { if (!drag.current) return;
                const [x, y] = drag.current; drag.current = [e.clientX, e.clientY];
                setAngle(([a, b]) => [a + (e.clientX - x) / 100, b + (e.clientY - y) / 100]); }} />
        <label>部件 <select aria-label="预览部件" value={selected} onChange={e => setSelected(Number(e.target.value))}>
            <option value={-1}>全部 ({parts.length})</option>
            {parts.map((part, i) => <option key={i} value={i}>{part.name}</option>)}
        </select></label>
        <label> 缩放 <input aria-label="模型缩放" type="range" min="0.3" max="3" step="0.1" value={zoom} onChange={e => setZoom(Number(e.target.value))} /></label>
        <span>{error || '拖动旋转 · 大模型预览可能抽样，导出包含完整网格'}</span>
    </div>;
}
