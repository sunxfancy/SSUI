import { cubic, fitCurve, moveNode, pressureAt, sampleCurve, vectorize } from './bezier';
import { hitStroke } from './drawing';
import type { DrawableObject, StrokePoint } from './types';
test('dense straight geometry compresses to two anchors but retains a pressure spike',()=>{
    const points=Array.from({length:1001},(_,i)=>({x:i,y:10,pressure:0.2+0.8*Math.max(0,1-Math.abs(i-500)/80)}));
    const path=fitCurve(points);
    expect(path.nodes.length).toBe(2);expect(path.pressure.length).toBeLessThan(10);
    for(let i=0;i<points.length;i++)expect(Math.abs(pressureAt(path.pressure,i/1000)-points[i].pressure)).toBeLessThanOrEqual(0.010001);
    expect(JSON.stringify(path).length).toBeLessThan(JSON.stringify(points).length/50);
});
test('smooth paths stay within fitting tolerance at original source parameters',()=>{
    const points=Array.from({length:1501},(_,i)=>({x:i*0.6,y:80*Math.sin(i/200),pressure:0.6}));
    const path=fitCurve(points,0.5);expect(path.nodes.length).toBeLessThan(30);
    let length=0;const ts=[0];for(let i=1;i<points.length;i++){length+=Math.hypot(points[i].x-points[i-1].x,points[i].y-points[i-1].y);ts.push(length);}
    let segment=1;
    points.forEach((p,i)=>{const t=ts[i]/length;while(segment<path.nodes.length-1 && path.nodes[segment][6]<t)segment++;
        const a=path.nodes[segment-1],b=path.nodes[segment];const q=cubic({x:a[0],y:a[1]},{x:a[4],y:a[5]},{x:b[2],y:b[3]},{x:b[0],y:b[1]},(t-a[6])/(b[6]-a[6]));
        expect(Math.hypot(q.x-p.x,q.y-p.y)).toBeLessThanOrEqual(0.50001);
    });
});
test('corners do not turn into a single overshooting arch; taps preserve maximum pressure',()=>{
    const path=fitCurve([{x:0,y:0,pressure:1},{x:100,y:100,pressure:1},{x:200,y:0,pressure:1}]);
    expect(path.nodes.length).toBeGreaterThanOrEqual(3);
    const tap=fitCurve([{x:5,y:8,pressure:0.1},{x:5,y:8,pressure:0.9},{x:5,y:8,pressure:0.2}]);
    expect(tap.nodes.length).toBe(1);expect(pressureAt(tap.pressure,0)).toBe(0.9);
});
test('vectorization removes the dense representation and anchor moves translate its handles',()=>{
    const o:DrawableObject={id:'line',type:'stroke',x:0,y:0,strokeWidth:10,points:Array.from({length:500},(_,i)=>({x:i,y:20,pressure:1}))};
    vectorize(o);expect(o.points).toBeUndefined();expect(o.curve!.source_count).toBe(500);
    const n=o.curve!.nodes[0],outX=n[4];moveNode(n,10,40);expect(n[4]).toBe(outX+10);expect(n[5]).toBe(40);
    expect(sampleCurve(o.curve!)[0]).toEqual({x:10,y:40,pressure:1});
    expect(hitStroke([{id:'layer',name:'Ink',visible:true,locked:false,opacity:1,objects:[o]}],10,40,0)?.object.id).toBe('line');
});
test('sampled curve coverage follows a distant handle bulge and pressure knots',()=>{
    const p=fitCurve([{x:0,y:0,pressure:0.2},{x:100,y:0,pressure:1}]);p.nodes[0][5]=400;p.nodes[1][3]=400;
    const samples=sampleCurve(p,0.1);expect(Math.max(...samples.map(p=>p.y))).toBeCloseTo(300);
    expect(samples[samples.length-1].pressure).toBeCloseTo(1);
});
