import React from 'react';
import type { DrawableObject, Layer, CurvePath, BezierNode } from './types';
import { paintLayers, strokePoint } from './drawing';
import type { BrushStyle } from './brushes';
import type { CanvasRenderer } from '../../../packages/canvas-engine/pkg/ssui_canvas_engine';
type Resource = {
    id: string;
    source: CanvasImageSource;
    width: number;
    height: number;
};
type GpuObject = {
    kind: 'stroke';
    stroke: {
        id: string;
        points: ReturnType<typeof strokePoint>[];
        width: number;
        color: number[];
    };
    erase: boolean;
    brush: BrushStyle;
    feather: number;
    curve?: CurvePath;
} | {
    kind: 'image';
    id: string;
    resource: string;
    x: number;
    y: number;
    width: number;
    height: number;
    rotation: number;
    erase: boolean;
};
let initPromise: Promise<typeof import('../../../packages/canvas-engine/pkg/ssui_canvas_engine')> | undefined;
export async function loadEngine() {
    if (!initPromise)
        initPromise = import('../../../packages/canvas-engine/pkg/ssui_canvas_engine').then(async (mod) => {
            await mod.default();
            return mod;
        }).catch(error => { initPromise = undefined; throw error; });
    return initPromise;
}
export class SceneAdapter {
    private objects = new WeakMap<DrawableObject, { object: GpuObject; resource?: Resource }>();
    private images = new WeakMap<object, string>();
    private nextImage = 0;
    private colorCanvas = document.createElement('canvas');
    private colors = new Map<string, number[]>();
    private previous = new Map<string, Layer['objects']>();
    private color(css: string) {
        if (!this.colors.has(css)) {
            this.colorCanvas.width = 1;
            this.colorCanvas.height = 1;
            const ctx = this.colorCanvas.getContext('2d', { willReadFrequently: true })!;
            ctx.fillStyle = css;
            ctx.fillRect(0, 0, 1, 1);
            if (this.colors.size >= 64) this.colors.delete(this.colors.keys().next().value!);
            this.colors.set(css, Array.from(ctx.getImageData(0, 0, 1, 1).data).map(v => v / 255));
        }
        return this.colors.get(css)!;
    }
    private convert(o: DrawableObject) {
        let cached = this.objects.get(o);
        if (cached) return cached;
        const erase = o.compositeOperation === 'destination-out';
        if (o.type === 'image' && o.image) {
            let id = this.images.get(o.image);
            if (!id) { id = `bitmap-${++this.nextImage}`; this.images.set(o.image, id); }
            cached = {
                object: { kind: 'image', id: o.id, resource: id, x: o.x, y: o.y,
                    width: o.width ?? o.image.width, height: o.height ?? o.image.height,
                    rotation: o.rotation ?? 0, erase },
                resource: { id, source: o.image, width: o.image.width, height: o.image.height },
            };
        } else if (o.type === 'stroke' && (o.points?.length || o.curve)) {
            const curve=o.curve ? {...o.curve,nodes:o.curve.nodes.map(n=>{
                const p=strokePoint(o,{x:n[0],y:n[1],pressure:1});
                const a=strokePoint(o,{x:n[2],y:n[3],pressure:1});
                const b=strokePoint(o,{x:n[4],y:n[5],pressure:1});
                return [p.x,p.y,a.x,a.y,b.x,b.y,n[6]] as BezierNode;
            })} : undefined;
            // All brushes remain compact source/mesh data; no per-stroke raster cache.
            cached = { object: { kind: 'stroke', erase, brush: o.strokeStyle ?? 'normal',
                feather: o.feather ?? 0,
                curve,
                stroke: { id: o.id, points: o.points?.map(p => strokePoint(o, p)) ?? [],
                    width: o.strokeWidth ?? 1, color: this.color(o.stroke ?? '#1f2937') },
            } };
        }
        if (cached) this.objects.set(o, cached);
        return cached;
    }
    build(layers: Layer[]) {
        const resources: Resource[] = [];
        const update = { layers: layers.map(layer => {
            const objects = layer.objects.flatMap(o => {
                const cached = this.convert(o);
                if (cached?.resource) resources.push(cached.resource);
                return cached ? [cached.object] : [];
            });
            const same = this.previous.get(layer.id) === layer.objects;
            this.previous.set(layer.id, layer.objects);
            return { id: layer.id, visible: layer.visible, opacity: layer.opacity,
                objects: same ? undefined : objects };
        }) };
        const active = new Set(layers.map(l => l.id));
        this.previous.forEach((_, id) => { if (!active.has(id)) this.previous.delete(id); });
        return { json: JSON.stringify(update), resources };
    }
}

interface Props {
    layers: Layer[];
    width: number;
    height: number;
    x: number;
    y: number;
    scale: number;
    onBackend: (backend: string, error?: string) => void;
    onStats?: (tiles: number, bytes: number) => void;
}
export default class GpuCanvas extends React.Component<Props, {
    gpu: boolean;
}> {
    state = { gpu: false };
    private gpuCanvas = React.createRef<HTMLCanvasElement>();
    private fallbackCanvas = React.createRef<HTMLCanvasElement>();
    private renderer?: CanvasRenderer;
    private adapter = new SceneAdapter();
    private uploaded = new Set<string>();
    private staging = document.createElement('canvas');
    private offscreen = document.createElement('canvas');
    private frame = 0;
    private disposed = false;
    private generation = 0;
    componentDidMount() { this.disposed = false; void this.initialize(); }
    componentWillUnmount() { this.disposed = true; this.generation++; cancelAnimationFrame(this.frame); this.renderer?.free(); this.renderer = undefined; }
    componentDidUpdate(prev: Props) {
        if (prev.layers !== this.props.layers || prev.width !== this.props.width || prev.height !== this.props.height
            || prev.x !== this.props.x || prev.y !== this.props.y || prev.scale !== this.props.scale)
            this.schedule();
    }
    private async initialize() {
        const generation = ++this.generation;
        try {
            if (!('gpu' in navigator))
                throw new Error('浏览器未提供 WebGPU');
            const mod = await loadEngine();
            if (this.disposed || generation !== this.generation)
                return;
            const renderer = await mod.CanvasRenderer.create(this.gpuCanvas.current!);
            if (this.disposed || generation !== this.generation) {
                renderer.free();
                return;
            }
            this.renderer = renderer;
            this.draw();
            this.setState({ gpu: true });
            this.props.onBackend('WebGPU');
            this.fallbackCanvas.current!.width = this.fallbackCanvas.current!.height = 1;
            this.offscreen.width = this.offscreen.height = 1;
        }
        catch (error) {
            if (!this.disposed && generation === this.generation)
                this.fallback(error);
        }
    }
    private fallback(error: unknown) {
        this.renderer?.free();
        this.renderer = undefined;
        this.uploaded.clear();
        this.staging.width = this.staging.height = 1;
        this.setState({ gpu: false });
        this.props.onBackend('Canvas2D', String(error));
        this.draw();
    }
    private schedule() {
        cancelAnimationFrame(this.frame);
        this.frame = requestAnimationFrame(() => {
            try {
                this.draw();
            }
            catch (error) {
                this.fallback(error);
            }
        });
    }
    private draw() {
        if (this.disposed)
            return;
        const { layers, width, height, x, y, scale } = this.props;
        const dpr = window.devicePixelRatio || 1, w = Math.max(1, Math.round(width * dpr)), h = Math.max(1, Math.round(height * dpr));
        const canvas = this.renderer ? this.gpuCanvas.current! : this.fallbackCanvas.current!;
        const resized = canvas.width !== w || canvas.height !== h;
        if (resized) {
            canvas.width = w;
            canvas.height = h;
        }
        if (this.renderer) {
            if (resized)
                this.renderer.resize(w, h);
            const { json, resources } = this.adapter.build(layers);
            const active = new Set(resources.map(r => r.id));
            this.uploaded.forEach(id => { if (!active.has(id))
                this.uploaded.delete(id); });
            for (const r of resources) {
                if (this.uploaded.has(r.id))
                    continue;
                this.staging.width = r.width;
                this.staging.height = r.height;
                const ctx = this.staging.getContext('2d', { willReadFrequently: true })!;
                ctx.drawImage(r.source, 0, 0);
                this.renderer.upload_image(r.id, r.width, r.height, new Uint8Array(ctx.getImageData(0, 0, r.width, r.height).data.buffer));
                this.uploaded.add(r.id);
            }
            if (this.staging.width > 1 || this.staging.height > 1) this.staging.width = this.staging.height = 1;
            this.renderer.render_scene_update(json, -x / scale, -y / scale, scale * dpr);
            const stats=JSON.parse(this.renderer.stats_json());
            this.props.onStats?.(stats.tiles, stats.gpu_payload_bytes);
        }
        else
            paintLayers(canvas.getContext('2d')!, this.offscreen, layers, w, h, x * dpr, y * dpr, scale * dpr);
    }
    render() {
        const style: React.CSSProperties = { position: 'absolute', inset: 0, pointerEvents: 'none', width: this.props.width, height: this.props.height };
        return <>
            <canvas aria-label="GPU 绘图画布" data-testid="gpu-canvas" ref={this.gpuCanvas} style={{ ...style, visibility: this.state.gpu ? 'visible' : 'hidden' }}/>
            <canvas aria-label="兼容绘图画布" ref={this.fallbackCanvas} style={{ ...style, visibility: this.state.gpu ? 'hidden' : 'visible' }}/>
        </>;
    }
}
