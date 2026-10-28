import type { DrawableObject, Layer, StrokePoint } from './types';
import { brushPressure } from './brushes';
import { strokeSamples } from './bezier';
export function strokePoint(object: DrawableObject, p: StrokePoint): StrokePoint {
    const r = (object.rotation ?? 0) * Math.PI / 180;
    return { x: object.x + p.x * Math.cos(r) - p.y * Math.sin(r),
        y: object.y + p.x * Math.sin(r) + p.y * Math.cos(r), pressure: p.pressure };
}
export function hitStroke(layers: Layer[], x: number, y: number, tolerance: number) {
    for (const layer of [...layers].reverse()) {
        if (!layer.visible || layer.locked || layer.opacity <= 0)
            continue;
        for (const object of [...layer.objects].reverse()) {
            if (object.type === 'image') {
                const r = -(object.rotation ?? 0) * Math.PI / 180;
                const px = (x - object.x) * Math.cos(r) - (y - object.y) * Math.sin(r);
                const py = (x - object.x) * Math.sin(r) + (y - object.y) * Math.cos(r);
                // An image on top blocks selection of a stroke underneath.
                if (px >= 0 && py >= 0 && px <= (object.width ?? 0) && py <= (object.height ?? 0))
                    return null;
            }
            const samples=strokeSamples(object,Math.max(0.05,Math.min(0.3,tolerance/3)));
            if (!samples.length)
                continue;
            const points = samples.map(p => strokePoint(object, p));
            for (let i = 0; i < points.length; i++) {
                const a = points[Math.max(0, i - 1)], b = points[i];
                const dx = b.x - a.x, dy = b.y - a.y, length = dx * dx + dy * dy;
                const t = length ? Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / length)) : 0;
                if (Math.hypot(x - a.x - dx * t, y - a.y - dy * t) <= tolerance + (object.strokeWidth ?? 1) * brushPressure(object.strokeStyle, a.pressure + (b.pressure - a.pressure) * t) / 2) {
                    return { layer, object };
                }
            }
        }
    }
    return null;
}
export function smoothPoints(points: StrokePoint[]): StrokePoint[] {
    return points.map((p, i) => i === 0 || i === points.length - 1 ? p : {
        x: (points[i - 1].x + 2 * p.x + points[i + 1].x) / 4,
        y: (points[i - 1].y + 2 * p.y + points[i + 1].y) / 4, pressure: p.pressure,
    });
}
// Small shared paper patterns for the compatibility renderer, never a per-line bitmap.
const paperPatterns = new Map<string, CanvasPattern>();
function paperPattern(ctx: CanvasRenderingContext2D, style: string, color: string) {
    const key=`${style}:${color}`;
    if (paperPatterns.has(key)) return paperPatterns.get(key)!;
    const canvas=document.createElement('canvas');canvas.width=128;canvas.height=128;
    const cx=canvas.getContext('2d')!;cx.fillStyle=color;cx.fillRect(0,0,128,128);
    const image=cx.getImageData(0,0,128,128);
    const hash=(x:number,y:number)=>{const v=Math.sin(x*127.1+y*311.7)*43758.5453;return v-Math.floor(v);};
    for (let y=0;y<128;y++) for (let x=0;x<128;x++) {
        const noise=hash(x,y), pool=hash(Math.floor(x/12),Math.floor(y/12));
        const alpha=style==='watercolor' ? 0.18+pool*0.24+noise*0.06 : noise>0.4 ? 0.45+noise*0.4 : 0.06;
        image.data[(y*128+x)*4+3]=Math.round(255*alpha);
    }
    cx.putImageData(image,0,0);
    const pattern=ctx.createPattern(canvas,'repeat')!;
    if (paperPatterns.size>=32) paperPatterns.delete(paperPatterns.keys().next().value!);
    paperPatterns.set(key,pattern);return pattern;
}
/** Compatibility painting uses shared patterns and transient layer scratch only. */
export function paintStroke(ctx: CanvasRenderingContext2D, object: DrawableObject) {
    const points = strokeSamples(object,0.2);
    ctx.save();
    ctx.translate(object.x, object.y);
    ctx.rotate((object.rotation ?? 0) * Math.PI / 180);
    ctx.strokeStyle = object.stroke ?? '#1f2937';
    ctx.fillStyle = ctx.strokeStyle;
    const style=object.strokeStyle ?? 'normal';
    ctx.globalAlpha = style === 'airbrush' ? 0.22 : style==='marker' ? 0.42 : 1;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    const feather = object.feather ?? 0;
    ctx.shadowColor = object.stroke ?? '#1f2937';
    ctx.shadowBlur = feather;
    if (style==='marker' || style==='watercolor' || style==='pencil') {
        if (style!=='marker') ctx.strokeStyle=paperPattern(ctx,style,object.stroke ?? '#1f2937');
        ctx.lineCap=style==='marker'?'square':'round';
        ctx.lineWidth=(object.strokeWidth ?? 1)*brushPressure(style,points.reduce((sum,p)=>sum+p.pressure,0)/Math.max(1,points.length));
        if (style==='watercolor') ctx.shadowBlur=Math.max(feather,ctx.lineWidth*0.12);
        ctx.beginPath();
        points.forEach((p,i)=>{if(i===0)ctx.moveTo(p.x,p.y);else ctx.lineTo(p.x,p.y);});
        if (points.length===1) ctx.lineTo(points[0].x+0.01,points[0].y);
        ctx.stroke();ctx.restore();return;
    }
    if (object.strokeStyle === 'texture')
        ctx.setLineDash([2, Math.max(2, (object.strokeWidth ?? 1) * 0.35)]);
    for (let i = 0; i < points.length; i++) {
        const a = points[Math.max(0, i - 1)], b = points[i];
        ctx.lineWidth = Math.max(0.5, (object.strokeWidth ?? 1) * brushPressure(object.strokeStyle,(a.pressure + b.pressure) / 2));
        ctx.beginPath();
        if (i === 0) {
            ctx.arc(a.x, a.y, ctx.lineWidth / 2, 0, 2 * Math.PI);
            ctx.fill();
        }
        else {
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
        }
    }
    ctx.restore();
}
export function paintLayers(ctx: CanvasRenderingContext2D, offscreen: HTMLCanvasElement, layers: Layer[], width: number, height: number, x: number, y: number, scale: number) {
    ctx.clearRect(0, 0, width, height);
    if (offscreen.width !== width)
        offscreen.width = width;
    if (offscreen.height !== height)
        offscreen.height = height;
    const layerCtx = offscreen.getContext('2d')!;
    for (const layer of layers) {
        if (!layer.visible || layer.opacity <= 0)
            continue;
        layerCtx.setTransform(1, 0, 0, 1, 0, 0);
        layerCtx.clearRect(0, 0, width, height);
        layerCtx.setTransform(scale, 0, 0, scale, x, y);
        for (const o of layer.objects) {
            layerCtx.globalCompositeOperation = o.compositeOperation ?? 'source-over';
            if (o.type === 'stroke')
                paintStroke(layerCtx, o);
            if (o.type === 'image' && o.image) {
                layerCtx.save();
                layerCtx.translate(o.x, o.y);
                layerCtx.rotate((o.rotation ?? 0) * Math.PI / 180);
                layerCtx.drawImage(o.image, 0, 0, o.width ?? o.image.width, o.height ?? o.image.height);
                layerCtx.restore();
            }
        }
        ctx.globalAlpha = layer.opacity;
        ctx.drawImage(offscreen, 0, 0);
    }
    ctx.globalAlpha = 1;
}
