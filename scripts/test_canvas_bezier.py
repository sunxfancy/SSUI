"""Pressure-preserving Bezier compression and real GPU rendering checks.
Requires the Canvas dev server, Python playwright/Pillow and installed Edge.
"""
import argparse
import io
import json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:7420/extension/ImageExtension/canvas/')
parser.add_argument('--output',default='test-artifacts/canvas-bezier')
args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/files/script?*',lambda r:r.fulfill(json=[]))
    page.goto(args.url);page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU')
    page.get_by_role('button',name='画笔',exact=True).click()
    page.mouse.move(200,260);page.mouse.down();page.mouse.move(1000,360,steps=200);page.mouse.up()
    page.get_by_role('button',name='编辑笔触',exact=True).click();page.mouse.click(600,310)
    expect(page.get_by_test_id('selected-stroke')).to_contain_text('201 点')
    expect(page.get_by_test_id('selected-stroke')).to_contain_text('2 锚点')
    # Outgoing handle starts one third along the fitted straight segment.
    page.mouse.move(466.667,293.333);page.mouse.down();page.mouse.move(466.667,453.333,steps=15);page.mouse.up()
    page.screenshot(path=str(out/'handles.png'))
    page.get_by_role('button',name='撤销',exact=True).click()
    page.get_by_label('笔触列表').select_option(label='笔触 1')
    expect(page.get_by_test_id('selected-stroke')).to_contain_text('2 锚点')
    report=page.evaluate('''async()=>{
      const {fitCurve}=await import('./canvas/bezier.ts');
      const {loadEngine}=await import('./canvas/GpuCanvas.tsx');const {CanvasRenderer}=await loadEngine();
      const canvas=document.createElement('canvas');canvas.width=1100;canvas.height=420;
      const r=await CanvasRenderer.create(canvas);
      const source=Array.from({length:4001},(_,i)=>({x:50+i/4,y:150+70*Math.sin(i/500),pressure:.2+.8*Math.max(0,1-Math.abs(i-2000)/600)}));
      const start=performance.now(),curve=fitCurve(source,.5),fit_ms=performance.now()-start;
      const render=async(points,curve)=>{r.render_scene(JSON.stringify({layers:[{id:'ink',visible:true,opacity:1,objects:[{
        kind:'stroke',stroke:{id:'s',points,width:40,color:[0,.2,.8,1]},curve}]}]}),0,0,1);await r.wait_idle();return JSON.parse(r.stats_json());};
      const raw=await render(source),fitted=await render([],curve);
      const encoding=new TextEncoder();
      const result={source_points:source.length,anchors:curve.nodes.length,pressure_knots:curve.pressure.length,
        source_numeric_values:source.length*3,curve_numeric_values:curve.nodes.length*7+curve.pressure.length*2,
        source_json_bytes:encoding.encode(JSON.stringify(source)).length,curve_json_bytes:encoding.encode(JSON.stringify(curve)).length,
        fit_ms,raw_gpu:raw,fitted_gpu:fitted};
      r.free();
      // A straight pressure-spike curve checks that native cubic rendering does
      // not interpolate only between the weak endpoint pressures.
      canvas.style.cssText='position:fixed;left:0;top:60px;z-index:10000;background:white';document.body.append(canvas);
      const renderer=await CanvasRenderer.create(canvas);window.bezierTestRenderer=renderer;
      const pressureSource=Array.from({length:1001},(_,i)=>({x:50+i,y:150,pressure:.1+.9*Math.max(0,1-Math.abs(i-500)/100)}));
      const pressureCurve=fitCurve(pressureSource,.5);
      window.bezierTestCurve=pressureCurve;
      window.drawBezierTest=()=>renderer.render_scene(JSON.stringify({layers:[{id:'pressure',visible:true,opacity:1,objects:[{
        kind:'stroke',stroke:{id:'pressure-stroke',points:[],width:80,color:[0,.2,.8,1]},curve:pressureCurve}]}]}),0,0,1);
      window.drawBezierTest();await renderer.wait_idle();
      return {...result,pressure_spike_knots:pressureCurve.pressure.length};
    }''')
    assert report['anchors']<40 and report['pressure_knots']<20,report
    assert report['curve_json_bytes']<report['source_json_bytes']/20,report
    assert report['fitted_gpu']['mesh_bytes']<report['raw_gpu']['mesh_bytes']/5,report
    image=Image.open(io.BytesIO(page.screenshot(path=str(out/'pressure.png')))).convert('RGB')
    assert image.getpixel((550,238))[2]>150 and image.getpixel((550,238))[0]<20
    assert image.getpixel((80,238))==(255,255,255)
    page.evaluate('''async()=>{const c=window.bezierTestCurve;c.nodes[0][5]+=200;c.nodes[1][3]+=200;window.drawBezierTest();await window.bezierTestRenderer.wait_idle();}''')
    image=Image.open(io.BytesIO(page.screenshot(path=str(out/'pressure-edited.png')))).convert('RGB')
    assert image.getpixel((550,360))[0]<20
    assert image.getpixel((550,210))==(255,255,255)
    page.evaluate('window.bezierTestRenderer.free()')
    assert not errors,errors
    report.update(browser=browser.version,errors=errors,
        accounting='JSON sizes measure serialized source geometry, not total JS heap. GPU mesh bytes are requested buffer payloads; fitting discards dense points in the retained editor document. Undo of an explicit conversion may retain the previous representation.')
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    browser.close()
