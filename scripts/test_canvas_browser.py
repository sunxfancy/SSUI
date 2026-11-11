"""Real Edge/Chromium Canvas regression and bounded WebGPU latency measurement.

Run against `yarn dev:canvas`. Requires playwright and pillow; browser defaults to
installed Edge. No AI backend is required: only script-list requests are mocked.
"""
import argparse
import io
import json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:7420/extension/ImageExtension/canvas/')
parser.add_argument('--channel', default='msedge')
parser.add_argument('--output', default='test-artifacts/canvas')
parser.add_argument('--skip-benchmark', action='store_true', help='Functional-only run, also supports a production preview URL')
parser.add_argument('--unsafe-webgpu', action='store_true', help='Opt in to the browser flag on test systems where WebGPU is otherwise blocked')
args = parser.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)

def draw(page, start, end, steps=30):
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=steps)
    page.mouse.up()
    page.wait_for_timeout(100)

def pixels(page, positions):
    # Read the browser compositor output. WebGPU canvas contents are transient and
    # drawImage from another event-loop task can legally return cleared pixels.
    png=page.screenshot(path=str(out/'last-check.png'))
    image=Image.open(io.BytesIO(png)).convert('RGBA')
    dpr=page.evaluate('window.devicePixelRatio')
    return [list(image.getpixel((round(position[0]*dpr),round(position[1]*dpr)))) for position in positions]

def near(pixel, expected, tolerance=4):
    assert all(abs(a-b) <= tolerance for a,b in zip(pixel,expected)), (pixel,expected)

with sync_playwright() as p:
    browser = p.chromium.launch(channel=args.channel, headless=True,
                                args=['--enable-unsafe-webgpu'] if args.unsafe_webgpu else [])
    page = browser.new_page(viewport={'width':1440,'height':1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route('**/files/script?*', lambda r:r.fulfill(json=[]))
    page.goto(args.url)
    page.wait_for_load_state('networkidle')
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU', timeout=20000)
    info = page.evaluate('''async()=>{const a=await navigator.gpu.requestAdapter();
      const i=a.info;return {vendor:i.vendor,architecture:i.architecture,device:i.device,
      description:i.description,isFallbackAdapter:i.isFallbackAdapter,userAgent:navigator.userAgent};}''')
    assert info['isFallbackAdapter'] is False, 'Hardware GPU is required for these measurements'

    # Real pointer input through the existing React/Konva editor.
    page.get_by_role('button',name='画笔',exact=True).click()
    draw(page,(200,250),(600,350))
    page.get_by_role('button',name='编辑笔触',exact=True).click()
    page.mouse.click(400,300)
    expect(page.get_by_test_id('selected-stroke')).to_contain_text('31 点')
    expect(page.get_by_test_id('selected-stroke')).to_contain_text('2 锚点')
    page.get_by_label('笔触线宽',exact=True).fill('32')
    page.get_by_label('笔触颜色',exact=True).fill('#e11d48')
    # A fitted straight line has two anchors. Drag its outgoing cubic handle.
    page.mouse.move(333.333,283.333);page.mouse.down();page.mouse.move(333.333,383.333,steps=10);page.mouse.up()
    page.get_by_role('button',name='画笔',exact=True).click()
    page.wait_for_timeout(150)
    near(pixels(page,[[400,338]])[0], [225,29,72,255])
    page.get_by_role('button',name='撤销',exact=True).click()
    page.wait_for_timeout(150)
    near(pixels(page,[[400,300]])[0], [225,29,72,255])
    page.get_by_role('button',name='编辑笔触',exact=True).click();page.mouse.click(400,300)
    page.get_by_role('button',name='平滑笔触',exact=True).click()
    page.get_by_role('button',name='删除笔触',exact=True).click()
    expect(page.get_by_label('笔触列表').locator('option')).to_have_count(1)
    page.keyboard.press('Control+z')
    expect(page.get_by_label('笔触列表').locator('option')).to_have_count(2)
    page.get_by_role('button',name='重做',exact=True).click()
    expect(page.get_by_label('笔触列表').locator('option')).to_have_count(1)

    # Imported red bitmap, then a separate blue layer with isolated erasure.
    image = io.BytesIO()
    Image.new('RGBA',(500,500),(255,0,0,255)).save(image,format='PNG')
    page.get_by_test_id('image-import').set_input_files({'name':'red.png','mimeType':'image/png','buffer':image.getvalue()})
    page.wait_for_timeout(200)
    near(pixels(page,[[300,270]])[0], [255,0,0,255])
    draw(page,(300,270),(364,334),steps=10)
    near(pixels(page,[[150,150]])[0],[255,255,255,255])
    page.get_by_title('新建图层',exact=True).click()
    page.get_by_role('button',name='画笔',exact=True).click()
    page.locator('.config-panel input[type=color]').fill('#0000ff')
    page.locator('.config-panel input[type=range]').nth(0).fill('80')
    draw(page,(200,270),(550,270))
    page.locator('.layer-card').first.locator('input[type=range]').fill('50')
    page.wait_for_timeout(150)
    near(pixels(page,[[300,270]])[0], [127,0,128,255])
    page.get_by_role('button',name='橡皮擦',exact=True).click()
    page.locator('.config-panel input[type=range]').nth(0).fill('40')
    draw(page,(300,240),(300,300))
    near(pixels(page,[[300,270]])[0], [255,0,0,255])
    page.get_by_role('button',name='编辑笔触',exact=True).click()
    page.get_by_label('笔触列表').select_option(label='橡皮擦 2')
    page.get_by_role('button',name='删除笔触',exact=True).click()
    page.wait_for_timeout(150)
    near(pixels(page,[[300,270]])[0], [127,0,128,255])
    page.get_by_role('button',name='撤销',exact=True).click()
    page.wait_for_timeout(150)
    near(pixels(page,[[300,270]])[0], [255,0,0,255])
    # Lock prevents drawing and clears editing selection.
    page.locator('.layer-card').first.get_by_title('锁定图层',exact=True).click()
    before = page.get_by_label('笔触列表').locator('option').count()
    page.get_by_role('button',name='画笔',exact=True).click();draw(page,(200,450),(500,450))
    assert page.get_by_label('笔触列表').locator('option').count()==before
    page.locator('.layer-card').first.get_by_title('解锁图层',exact=True).click()
    page.locator('.layer-card').first.get_by_title('隐藏图层',exact=True).click()
    page.wait_for_timeout(150)
    near(pixels(page,[[400,270]])[0],[255,0,0,255])
    page.locator('.layer-card').first.get_by_title('显示图层',exact=True).click()
    page.get_by_role('button',name='编辑笔触',exact=True).click()
    page.get_by_label('笔触列表').select_option(label='橡皮擦 2')
    expect(page.get_by_role('button',name='编辑笔触',exact=True)).to_have_class('tool-button active')
    page.wait_for_timeout(150)
    page.screenshot(path=str(out/'editor.png'),full_page=True)

    # Direct WASM renderer measurements include serialization, WASM work, command
    # submission and an explicit GPU completion fence. They exclude React/UI cost.
    result = None if args.skip_benchmark else page.evaluate('''async()=>{
      const {loadEngine,SceneAdapter}=await import('./canvas/GpuCanvas.tsx');
      const {CanvasRenderer}=await loadEngine();
      const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;
      const r=await CanvasRenderer.create(canvas);
      const summary=values=>{values.sort((a,b)=>a-b);return {p50_ms:values[Math.floor(values.length*.5)],p95_ms:values[Math.floor(values.length*.95)]};};
      const results=[];
      for(const count of [100,1000]){
        const layers=Array.from({length:4},(_,i)=>({id:`bench-layer-${i}`,name:`Layer ${i}`,locked:false,visible:true,opacity:1,objects:[]}));
        const bitmapCanvas=document.createElement('canvas');bitmapCanvas.width=512;bitmapCanvas.height=512;
        const ctx=bitmapCanvas.getContext('2d');ctx.fillStyle='#f0f8ff';ctx.fillRect(0,0,512,512);
        const bitmap=await createImageBitmap(bitmapCanvas);
        for(let i=0;i<4;i++)layers[i].objects.push({id:`image-${i}`,type:'image',image:bitmap,x:i*150,y:50,width:512,height:512});
        for(let i=0;i<count;i++)layers[i%4].objects.push({type:'stroke',id:`s-${i}`,x:0,y:0,strokeWidth:3,stroke:'#194db2',
          points:Array.from({length:64},(_,j)=>({x:40+j*17,y:30+(i%80)*8+Math.sin(j*.2)*5,pressure:.3+j/100}))});
        const adapter=new SceneAdapter(),uploaded=new Set();
        const render=x=>{
          const update=adapter.build(layers);
          for(const resource of update.resources){if(uploaded.has(resource.id))continue;
            const c=document.createElement('canvas');c.width=resource.width;c.height=resource.height;
            const cx=c.getContext('2d');cx.drawImage(resource.source,0,0);
            r.upload_image(resource.id,c.width,c.height,new Uint8Array(cx.getImageData(0,0,c.width,c.height).data.buffer));uploaded.add(resource.id);
          }
          r.render_scene_update(update.json,x,0,1);
        };
        let start=performance.now();render(0);await r.wait_idle();
        const cold_ms=performance.now()-start;
        for(const mode of ['cached','edit_one_stroke','pan_all_layers']){
          const submit=[],complete=[];
          for(let frame=0;frame<35;frame++){
            if(mode==='edit_one_stroke'){
              const objects=[...layers[3].objects],o=objects.at(-1),points=[...o.points];
              points[32]={...points[32],y:points[32].y+.25};objects[objects.length-1]={...o,points};layers[3]={...layers[3],objects};
            }
            const begin=performance.now();
            render(mode==='pan_all_layers'?frame:0);
            const submitted=performance.now();await r.wait_idle();
            if(frame>=5){submit.push(submitted-begin);complete.push(performance.now()-begin);}
          }
          results.push({strokes:count,samples_per_stroke:64,layers:4,images:4,image_size:[512,512],mode,cold_ms,submission:summary(submit),gpu_completed:summary(complete)});
        }
        bitmap.close();
      }
      r.free();return {width:1280,height:720,frames_per_case:30,cases:results};
    }''')
    # Verify the same editing flow remains usable without WebGPU.
    fallback = browser.new_page(viewport={'width':1440,'height':1000})
    fallback.on('pageerror',lambda e:errors.append(str(e)))
    fallback.add_init_script("Object.defineProperty(navigator,'gpu',{value:undefined});")
    fallback.route('**/files/script?*',lambda r:r.fulfill(json=[]))
    fallback.goto(args.url);fallback.wait_for_load_state('networkidle')
    expect(fallback.get_by_test_id('render-backend')).to_have_text('Canvas2D')
    fallback.get_by_role('button',name='画笔',exact=True).click();draw(fallback,(200,250),(600,350))
    fallback.get_by_role('button',name='编辑笔触',exact=True).click();fallback.mouse.click(400,300)
    expect(fallback.get_by_test_id('selected-stroke')).to_be_visible()
    fallback.get_by_role('button',name='删除笔触',exact=True).click()
    expect(fallback.get_by_label('笔触列表').locator('option')).to_have_count(1)
    fallback.screenshot(path=str(out/'fallback.png'))
    # High-DPI backing store, camera anchoring and picking through the real UI.
    highdpi=browser.new_page(viewport={'width':1200,'height':900},device_scale_factor=2)
    highdpi.on('pageerror',lambda e:errors.append(str(e)))
    highdpi.route('**/files/script?*',lambda r:r.fulfill(json=[]))
    highdpi.goto(args.url);highdpi.wait_for_load_state('networkidle')
    expect(highdpi.get_by_test_id('render-backend')).to_have_text('WebGPU')
    highdpi.get_by_role('button',name='画笔',exact=True).click();draw(highdpi,(200,250),(550,350),20)
    highdpi.mouse.move(375,300);highdpi.mouse.wheel(0,-100);highdpi.wait_for_timeout(150)
    highdpi.get_by_role('button',name='编辑笔触',exact=True).click();highdpi.mouse.click(375,300)
    expect(highdpi.get_by_test_id('selected-stroke')).to_be_visible()
    highdpi.get_by_role('button',name='画笔',exact=True).click()
    highdpi.mouse.move(375,300);highdpi.mouse.down(button='middle');highdpi.mouse.move(475,400,steps=10);highdpi.mouse.up(button='middle')
    highdpi.get_by_role('button',name='编辑笔触',exact=True).click();highdpi.mouse.click(475,400)
    expect(highdpi.get_by_test_id('selected-stroke')).to_be_visible()
    highdpi.set_viewport_size({'width':1280,'height':900});highdpi.wait_for_timeout(200)
    assert highdpi.get_by_test_id('gpu-canvas').evaluate('(c)=>c.width')==2560
    highdpi.screenshot(path=str(out/'highdpi.png'))
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU')
    expect(highdpi.get_by_test_id('render-backend')).to_have_text('WebGPU')
    assert not errors, errors
    report={'browser':browser.version,'adapter':info,'unsafe_webgpu_flag':args.unsafe_webgpu,'functional_checks':'passed','errors':errors,'benchmark':result,
            'scope':'Headless installed Edge. Timings include the real SceneAdapter, incremental serialization, WASM and a GPU completion fence; exclude React input handling. Cold time includes bitmap upload. No frame-rate or cross-device guarantee.'}
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    browser.close()
