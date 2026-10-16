import type { BezierNode, CurvePath, DrawableObject, StrokePoint } from './types';
type XY = { x: number; y: number };
const distance = (a: XY, b: XY) => Math.hypot(a.x-b.x,a.y-b.y);
const unit = (x: number,y: number): XY => {const n=Math.hypot(x,y);return n>1e-10?{x:x/n,y:y/n}:{x:1,y:0};};
export function cubic(a: XY,b: XY,c: XY,d: XY,t: number): XY {
    const s=1-t;
    return {x:s*s*s*a.x+3*s*s*t*b.x+3*s*t*t*c.x+t*t*t*d.x,
        y:s*s*s*a.y+3*s*s*t*b.y+3*s*t*t*c.y+t*t*t*d.y};
}
export function pressureAt(profile: CurvePath['pressure'],t: number) {
    let lo=0,hi=profile.length-1;
    while(lo+1<hi) {const mid=(lo+hi)>>1;if(profile[mid][0]<=t)lo=mid;else hi=mid;}
    const a=profile[lo],b=profile[hi];
    return a[1]+(b[1]-a[1])*Math.max(0,Math.min(1,(t-a[0])/Math.max(1e-12,b[0]-a[0])));
}
export function fitCurve(input: StrokePoint[], tolerance=0.5, pressureError=0.01): CurvePath {
    if (!input.length) throw new Error('Empty stroke');
    const points: XY[]=[],times:number[]=[];let total=0;
    for(let i=0;i<input.length;i++) {if(i)total+=distance(input[i-1],input[i]);times.push(total);}
    const peak=input.reduce((max,p)=>Math.max(max,p.pressure),0);
    if(total<1e-8) return {nodes:[[input[0].x,input[0].y,input[0].x,input[0].y,input[0].x,input[0].y,0]],
        pressure:[[0,peak],[1,peak]],source_count:input.length,tolerance};
    const profile: [number,number][]=[];
    input.forEach((p,i)=>{
        const t=times[i]/total;
        if(profile.length && profile[profile.length-1][0]===t) profile[profile.length-1][1]=Math.max(profile[profile.length-1][1],p.pressure);
        else profile.push([t,p.pressure]);
        if(!points.length || distance(points[points.length-1],p)>1e-8) points.push({x:p.x,y:p.y});
    });
    // Pressure is simplified independently: even a geometrically straight line
    // keeps its pressure spikes instead of reducing them to endpoint widths.
    const keep=new Set([0,profile.length-1]),stack:[[number,number]]=[[0,profile.length-1]];
    while(stack.length) {
        const [a,b]=stack.pop()!;let error=pressureError,split=-1;
        for(let i=a+1;i<b;i++) {const u=(profile[i][0]-profile[a][0])/(profile[b][0]-profile[a][0]);
            const e=Math.abs(profile[i][1]-(profile[a][1]+(profile[b][1]-profile[a][1])*u));
            if(e>error){error=e;split=i;}}
        if(split>=0){keep.add(split);stack.push([a,split],[split,b]);}
    }
    const ptime=[0];for(let i=1;i<points.length;i++)ptime.push(ptime[i-1]+distance(points[i-1],points[i]));
    const nodes:BezierNode[]=[];
    const emit=(a:XY,b:XY,c:XY,d:XY,start:number,end:number)=>{
        if(!nodes.length)nodes.push([a.x,a.y,a.x,a.y,b.x,b.y,start]);
        else {nodes[nodes.length-1][4]=b.x;nodes[nodes.length-1][5]=b.y;}
        nodes.push([d.x,d.y,c.x,c.y,d.x,d.y,end]);
    };
    // Iterative Schneider-style endpoint-tangent least-squares fitting. Split at
    // the largest paired-sample error; no recursive call-stack growth on scribbles.
    const jobs:{a:number;b:number;left:XY;right:XY}[]=[{a:0,b:points.length-1,
        left:unit(points[1].x-points[0].x,points[1].y-points[0].y),
        right:unit(points[points.length-2].x-points[points.length-1].x,points[points.length-2].y-points[points.length-1].y)}];
    while(jobs.length) {
        const job=jobs.pop()!,{a,b,left,right}=job,A=points[a],D=points[b];
        if(b-a===1){emit(A,{x:A.x+(D.x-A.x)/3,y:A.y+(D.y-A.y)/3},
            {x:D.x-(D.x-A.x)/3,y:D.y-(D.y-A.y)/3},D,ptime[a]/total,ptime[b]/total);continue;}
        const length=ptime[b]-ptime[a];let c00=0,c01=0,c11=0,x0=0,x1=0;
        for(let i=a;i<=b;i++) {
            const t=(ptime[i]-ptime[a])/length,s=1-t,b1=3*s*s*t,b2=3*s*t*t;
            const ax=left.x*b1,ay=left.y*b1,bx=right.x*b2,by=right.y*b2;
            const qx=points[i].x-A.x*(s*s*s+b1)-D.x*(b2+t*t*t),qy=points[i].y-A.y*(s*s*s+b1)-D.y*(b2+t*t*t);
            c00+=ax*ax+ay*ay;c01+=ax*bx+ay*by;c11+=bx*bx+by*by;x0+=ax*qx+ay*qy;x1+=bx*qx+by*qy;
        }
        const det=c00*c11-c01*c01,fallback=distance(A,D)/3;
        let alpha=det>1e-12?(x0*c11-x1*c01)/det:fallback,beta=det>1e-12?(c00*x1-c01*x0)/det:fallback;
        if(alpha<length*1e-6 || beta<length*1e-6 || alpha>length*2 || beta>length*2)alpha=beta=fallback;
        const B={x:A.x+left.x*alpha,y:A.y+left.y*alpha},C={x:D.x+right.x*beta,y:D.y+right.y*beta};
        let max=0,split=(a+b)>>1;
        for(let i=a+1;i<b;i++){const e=distance(points[i],cubic(A,B,C,D,(ptime[i]-ptime[a])/length));if(e>max){max=e;split=i;}}
        for(let i=a+1;i<=b;i++) {
            const t=((ptime[i]+ptime[i-1])/2-ptime[a])/length;
            const e=distance({x:(points[i].x+points[i-1].x)/2,y:(points[i].y+points[i-1].y)/2},cubic(A,B,C,D,t));
            if(e>max){max=e;split=Math.max(a+1,Math.min(b-1,i));}
        }
        if(max<=tolerance || b-a===1)emit(A,B,C,D,ptime[a]/total,ptime[b]/total);
        else {
            const tangent=unit(points[split-1].x-points[split+1].x,points[split-1].y-points[split+1].y);
            jobs.push({a:split,b,left:{x:-tangent.x,y:-tangent.y},right},{a,b:split,left,right:tangent});
        }
    }
    nodes[nodes.length-1][6]=1;
    return {nodes,pressure:[...keep].sort((a,b)=>a-b).map(i=>profile[i]),source_count:input.length,tolerance};
}
export function sampleCurve(curve: CurvePath,tolerance=0.3): StrokePoint[] {
    const {nodes,pressure}=curve;
    const out:StrokePoint[]=[{x:nodes[0][0],y:nodes[0][1],pressure:pressureAt(pressure,0)}];
    for(let i=1;i<nodes.length;i++) {
        const a=nodes[i-1],b=nodes[i],A={x:a[0],y:a[1]},B={x:a[4],y:a[5]},C={x:b[2],y:b[3]},D={x:b[0],y:b[1]};
        const ts=new Set<number>([1]);
        const jobs:[number,number,number][]=[[0,1,0]];
        while(jobs.length){const [lo,hi,depth]=jobs.pop()!,p=cubic(A,B,C,D,lo),q=cubic(A,B,C,D,hi);
            let error=0;for(const f of [.25,.5,.75]){const c=cubic(A,B,C,D,lo+(hi-lo)*f);error=Math.max(error,Math.hypot(c.x-p.x-(q.x-p.x)*f,c.y-p.y-(q.y-p.y)*f));}
            if(error>tolerance && depth<16){const mid=(lo+hi)/2;jobs.push([lo,mid,depth+1],[mid,hi,depth+1]);}else ts.add(hi);
        }
        for(const [t] of pressure)if(t>a[6] && t<b[6])ts.add((t-a[6])/(b[6]-a[6]));
        for(const t of [...ts].sort((a,b)=>a-b)){const p=cubic(A,B,C,D,t);out.push({...p,pressure:pressureAt(pressure,a[6]+(b[6]-a[6])*t)});}
    }
    return out;
}
export function strokeSamples(o: DrawableObject,tolerance=0.3) {return o.curve?sampleCurve(o.curve,tolerance):o.points ?? [];}
export function vectorize(o: DrawableObject,tolerance=0.5) {
    const original=o.curve?.source_count;
    const points=strokeSamples(o,Math.min(0.1,tolerance/4));
    if (!points.length) return;
    o.curve=fitCurve(points,tolerance,Math.min(0.01,0.25/(o.strokeWidth ?? 1)));
    if(original!==undefined)o.curve.source_count=original;
    delete o.points;
    return o.curve;
}
export function moveNode(node: BezierNode,x: number,y: number) {
    const dx=x-node[0],dy=y-node[1];node[0]=x;node[1]=y;node[2]+=dx;node[3]+=dy;node[4]+=dx;node[5]+=dy;
}
