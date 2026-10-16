"""Verify the input/export bridge includes retained Bezier ink, without overlays."""
import base64
import io
from PIL import Image
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.route('**/files/script?*',lambda r:r.fulfill(json=[]))
    page.goto('http://127.0.0.1:7420/extension/ImageExtension/canvas/?input=1')
    expect(page.get_by_test_id('render-backend')).to_have_text('WebGPU')
    page.get_by_role('button',name='画笔',exact=True).click()
    page.mouse.move(200,260);page.mouse.down();page.mouse.move(600,260,steps=100);page.mouse.up()
    def export():
        return page.evaluate('''()=>new Promise(resolve=>{
          const listener=e=>{if(e.data?.type==='ssui-canvas-result'){removeEventListener('message',listener);resolve(e.data);}};
          addEventListener('message',listener);postMessage({type:'ssui-canvas-export'},location.origin);
        })''')
    fixed=export()
    def pixels(result):
        return Image.open(io.BytesIO(base64.b64decode(result['image'].split(',')[1]))).convert('RGBA')
    image=pixels(fixed)
    assert image.getbbox() is not None
    assert image.getpixel((400,260))[3]>0
    assert image.getpixel((400,100))[3]==0
    # Loading a transparent image clears ink and switches to unbounded export.
    blank=io.BytesIO();Image.new('RGBA',(1,1)).save(blank,format='PNG')
    page.evaluate('''image=>postMessage({type:'ssui-canvas-load',image,settings:{unbounded:true,width:512,height:512,margin:32}},location.origin)''',
        'data:image/png;base64,'+base64.b64encode(blank.getvalue()).decode())
    page.wait_for_timeout(100)
    page.mouse.move(200,260);page.mouse.down();page.mouse.move(600,260,steps=100);page.mouse.up()
    unbounded=export();image=pixels(unbounded)
    assert image.getbbox() is not None
    assert image.width<1000 and image.height<300
    print({'fixed':fixed['bounds'],'unbounded':unbounded['bounds'],'ink_export':'passed'})
    browser.close()
