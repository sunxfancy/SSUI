"""Real-browser brush appearance, sparse cache accounting and reclamation checks.
Run against yarn dev:canvas. Requires playwright, pillow and installed Edge.
"""
import argparse
import io
import json
import math
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:7420/extension/ImageExtension/canvas/')
parser.add_argument('--output',default='test-artifacts/canvas-brushes')
args=parser.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/files/script?*',lambda r:r.fulfill(json=[]))
    page.goto(args.url);page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU',timeout=20000)
    page.get_by_role('button',name='画笔',exact=True).click()
    rows=[]
    for i,style in enumerate(['pen','marker','watercolor','pencil','airbrush','texture']):
        y=210+i*112
        page.get_by_label('画笔类型',exact=True).select_option(style)
        page.locator('.config-panel input[type=color]').fill('#4169ba')
        page.mouse.move(230,y);page.mouse.down()
        for step in range(1,41):
            page.mouse.move(230+step*20,y+math.sin(step/6)*18)
        page.mouse.up();page.wait_for_timeout(100)
        rows.append((style,y))
    expect(page.locator('.layer-card')).to_have_count(1)
    expect(page.get_by_label('笔触列表').locator('option')).to_have_count(7)
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU')
    png=page.screenshot(path=str(out/'brushes.png'))
    image=Image.open(io.BytesIO(png)).convert('RGB')
    appearances=[]
    for style,y in rows:
        crop=image.crop((240,y-40,1020,y+40))
        values=(crop.getpixel((x,y)) for y in range(crop.height) for x in range(crop.width))
        ink=[v for v in values if v[2]>v[0]+8 and v[2]>v[1]+3]
        assert len(ink)>100,(style,'no visible ink')
        appearances.append({'brush':style,'colored_pixels':len(ink),
            'mean_rgb':[round(sum(v[c] for v in ink)/len(ink),2) for c in range(3)]})
    assert appearances[1]['colored_pixels']>appearances[0]['colored_pixels']*2
    assert appearances[2]['colored_pixels']>appearances[3]['colored_pixels']*2
    # Changing the selected brush retains source points, identity and undo behavior.
    page.get_by_label('笔触列表').select_option(label='笔触 1')
    points=page.get_by_test_id('selected-stroke').text_content()
    page.get_by_label('笔触画笔类型',exact=True).select_option('watercolor')
    expect(page.get_by_test_id('selected-stroke')).to_have_text(points)
    page.get_by_role('button',name='撤销',exact=True).click()
    page.get_by_label('笔触列表').select_option(label='笔触 1')
    expect(page.get_by_label('笔触画笔类型',exact=True)).to_have_value('pen')
    page.get_by_role('button',name='删除笔触',exact=True).click()
    expect(page.locator('.layer-card')).to_have_count(1)
    page.get_by_role('button',name='撤销',exact=True).click()
    # A tiny stroke in a 4096-square viewport must allocate ONE shared tile.
    memory=page.evaluate('''async()=>{
      const {loadEngine}=await import('./canvas/GpuCanvas.tsx');const {CanvasRenderer}=await loadEngine();
      const canvas=document.createElement('canvas');canvas.width=4096;canvas.height=4096;
      const r=await CanvasRenderer.create(canvas);
      const object=(id,brush='normal')=>({kind:'stroke',brush,stroke:{id,width:8,color:[.2,.4,.8,1],
        points:[{x:30,y:30,pressure:1},{x:70,y:60,pressure:1}]}});
      const render=async(objects,x=0,y=0)=>{r.render_scene(JSON.stringify({layers:[{id:'ink',visible:true,opacity:1,objects}]}),x,y,1);await r.wait_idle();return JSON.parse(r.stats_json());};
      const tiny=await render([object('s')]);
      const overlapping=await render(Array.from({length:100},(_,i)=>object(`s${i}`,['pen','marker','watercolor','pencil'][i%4])));
      const diagonal=object('diagonal');diagonal.stroke.points=[{x:20,y:20,pressure:1},{x:4000,y:4000,pressure:1}];
      const long_diagonal=await render([diagonal]);
      const offscreen=await render([diagonal],5000,5000);
      const restored=await render([object('s')]);
      const erased=object('eraser');erased.erase=true;
      const eraser_only=await render([erased]);
      const empty=await render([]);
      r.free();return {viewport:[4096,4096],previous_full_layer_and_msaa_bytes:4096*4096*4*5,
        tiny,overlapping,long_diagonal,offscreen,restored,eraser_only,empty};
    }''')
    assert memory['tiny']['tiles']==1,memory
    assert memory['overlapping']['tiles']==1 and memory['overlapping']['images']==0,memory
    assert memory['long_diagonal']['tiles']<60,memory
    for name in ['empty','offscreen','eraser_only']:
        assert memory[name]['tiles']==0 and memory[name]['gpu_payload_bytes']==0,(name,memory[name])
    assert memory['restored']['tiles']==1
    assert memory['tiny']['gpu_payload_bytes'] < memory['previous_full_layer_and_msaa_bytes']/100
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU')
    # User layer count must not grow the number of viewport-sized Konva canvases.
    canvases=page.locator('.konvajs-content canvas').count()
    page.get_by_title('新建图层',exact=True).click()
    page.get_by_title('新建图层',exact=True).click()
    expect(page.locator('.layer-card')).to_have_count(3)
    assert page.locator('.konvajs-content canvas').count()==canvases
    assert not errors,errors
    report={'browser':browser.version,'brushes':appearances,'memory':memory,'errors':errors,
      'accounting':'Requested resident GPU cache payloads only: RGBA tiles + shared MSAA + mesh/uniform buffers + source image textures. Excludes output surface, driver allocator overhead and CPU/JS source/history. Not process RSS.'}
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    browser.close()
