#!/usr/bin/env node
// Real Tauri/WebKit smoke: clean install, workflow execution and media previews.
const fs = require('node:fs');
const path = require('node:path');
const {spawn,spawnSync} = require('node:child_process');
const assert = require('node:assert/strict');
const tar = require('tar');
const root = path.resolve(__dirname, '..');
const artifact = process.env.SSUI_SMOKE_ARTIFACT || path.join(root, '.build/desktop-linux-smoke', String(Date.now()));
const install = path.join(artifact, 'Fresh Linux install');
const project = path.join(artifact, 'Generated workflow');
let app = process.env.SSUI_LINUX_APP;
let appdir = process.env.SSUI_LINUX_APPDIR;
const tauri = process.env.SSUI_TAURI_DRIVER || 'tauri-driver';
const webkit = process.env.SSUI_WEBKIT_DRIVER || 'WebKitWebDriver';
const port = Number(process.env.SSUI_WEBDRIVER_PORT || 4446);
const base = `http://127.0.0.1:${port}`;
let driver, session;
const pause = ms => new Promise(resolve=>setTimeout(resolve,ms));
async function request(route, body, method) {
  const response = await fetch(base+route,{method:method || (body===undefined?'GET':'POST'),
    headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
  const result = await response.json();
  if (result.value?.error) throw Error(JSON.stringify(result.value));
  return result.value;
}
async function evaluate(script, args=[]) {return request(`/session/${session}/execute/sync`,{script,args});}
async function until(fn, timeout=30000) {
  const end=Date.now()+timeout;let error;
  while(Date.now()<end){try{const result=await fn();if(result)return result;}catch(e){if(e.fatal)throw e;error=e;}await pause(500);}
  throw Error('Timed out: '+(error?.message || 'condition not met'));
}
async function start() {
  const log=fs.openSync(path.join(artifact,'driver.log'),'a');
  driver=spawn('xvfb-run',['-a','dbus-run-session','--',tauri,'--port',String(port),'--native-port',String(port+1),'--native-driver',webkit],{
    detached:true,stdio:['ignore',log,log],env:{...process.env,
      XDG_CONFIG_HOME:path.join(artifact,'config'),XDG_DATA_HOME:path.join(artifact,'data'),
      ...(process.env.SSUI_GST_PLUGIN_PATH ? {GST_PLUGIN_PATH:process.env.SSUI_GST_PLUGIN_PATH} : {}),XDG_CACHE_HOME:path.join(root,'.build/cache'),TMPDIR:path.join(root,'.build/tmp'),
      ...(appdir ? {APPDIR:appdir} : {}),GDK_BACKEND:'x11',WEBKIT_DISABLE_DMABUF_RENDERER:'1',SSUI_SERVER_HOST:'127.0.0.1',SSUI_SERVER_PORT:'7422'}});
  fs.closeSync(log);
  await until(()=>request('/status').then(x=>x.ready),20000);
  const result=await request('/session',{capabilities:{alwaysMatch:{'tauri:options':{application:app}}}});
  session=result.sessionId;
  fs.writeFileSync(path.join(artifact,'webdriver-session.txt'),session);
  await until(()=>evaluate('return document.body.innerText').then(x=>x.length>10));
  await until(()=>evaluate("return document.visibilityState === 'visible'"));
}
async function stop() {
  if(session){try{await request('/session/'+session,undefined,'DELETE');}catch{}session=undefined;}
  if(driver){
    const group=driver.pid;
    try{process.kill(-group,'SIGTERM');}catch{}
    await pause(1000);
    // A stopped WebDriver can leave Python waiting on a pending task.
    // Only this test's isolated process group is eligible for forced cleanup.
    try{process.kill(-group,'SIGKILL');}catch{}
    driver=undefined;
  }
}
async function setInput(selector,value) {
  await evaluate(`const input=document.querySelector(arguments[0]);if(!input)throw Error(arguments[0]);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,arguments[1]);input.dispatchEvent(new Event('input',{bubbles:true}));`,[selector,value]);
}
async function clickText(text,selector='button') {
  await evaluate(`const item=Array.from(document.querySelectorAll(arguments[1])).find(x=>(x.innerText.trim()===arguments[0] || (arguments[0]==='Run' && x.innerText.trim()==='运行')));if(!item)throw Error('Missing '+arguments[0]);item.click();`,[text,selector]);
}
for (const signal of ['SIGTERM','SIGINT']) process.on(signal,()=>{stop().finally(()=>process.exit(1))});
(async()=>{
  assert.equal(process.platform,'linux');
  fs.mkdirSync(install,{recursive:true});fs.mkdirSync(project,{recursive:true});
  if (!app) {
    const directory=path.join(root,'.build/linux-desktop-target/release/bundle/deb');
    const candidates=fs.readdirSync(directory).filter(x=>x.endsWith('.deb')).map(x=>path.join(directory,x));
    candidates.sort((a,b)=>fs.statSync(b).mtimeMs-fs.statSync(a).mtimeMs);
    const deb=process.env.SSUI_LINUX_DEB || candidates[0];
    assert.ok(deb,'Build the Debian package first');
    const extractedRoot=path.join(artifact,'installed-app');
    const extraction=spawnSync('dpkg-deb',['-x',deb,extractedRoot],{encoding:'utf8'});
    assert.equal(extraction.status,0,extraction.stderr);
    app=path.join(extractedRoot,'usr/bin/ssui');
  }
  assert.ok(fs.existsSync(app),app);
  console.log('ARTIFACTS',artifact);
  // Replays exercise the new package against the same independently created venv.
  if (process.env.SSUI_SMOKE_ARTIFACT) {
    const resources=path.resolve(path.dirname(app),'../lib/ssui/resources');
    await tar.x({file:path.join(resources,'app.tar.gz'),cwd:install});
    for (const file of fs.readdirSync(path.join(resources,'extensions')).filter(x=>x.endsWith('.tar.gz'))) {
      await tar.x({file:path.join(resources,'extensions',file),cwd:path.join(install,'extensions')});
    }
  }
  await start();
  const settingsFile=path.join(artifact,'data/com.ssui.app/settings.json');
  if (!fs.existsSync(settingsFile)) {
  await setInput('input[placeholder="Enter installation directory"]',install);
  await clickText('Install');
  let previous='', sawLinuxLock=false;
  await until(async()=>{
    if (fs.existsSync(settingsFile) && fs.existsSync(path.join(install,'.venv/.packages_installed'))) return true;
    const body=await evaluate('return document.body.innerText');
    if (body.includes('linux.lock')) sawLinuxLock=true;
    if (body.trim()) fs.writeFileSync(path.join(artifact,'install-ui.txt'),body);
    if(body.includes('安装中止') || body.includes('安装过程中出错')){const error=new Error(body);error.fatal=true;throw error;}
    if(body!==previous){console.log(body.slice(-650));previous=body;}
    return fs.existsSync(path.join(install,'server/server.py')) && fs.existsSync(path.join(install,'.venv/.packages_installed'));
  },900000);
  assert.ok(sawLinuxLock,'Linux dependency lock was not observed');
  assert.ok(fs.existsSync(path.join(install,'extensions/Video/ssui_video/Wan21.py')));
  assert.ok(fs.existsSync(path.join(install,'extensions/3D-Model/vendor/trellis/__init__.py')));
  assert.ok(fs.existsSync(path.join(install,'.venv/native-cuda/runtime.json')));
  console.log('DESKTOP_CLEAN_INSTALL_PASS');
  await pause(2500);await stop();await start();
  }
  await until(async()=>{
    const response=await fetch('http://127.0.0.1:7422/openapi.json',{signal:AbortSignal.timeout(2000)});
    return response.ok;
  },90000);
  const device=await fetch('http://127.0.0.1:7422/api/device').then(x=>x.json());
  assert.notEqual(device,'cpu');
  console.log('DESKTOP_BACKEND_START_PASS',device);
  const state=await evaluate('return {text:document.body.innerText, buttons:Array.from(document.querySelectorAll("button")).map(x=>({text:x.innerText,title:x.title}))}');
  fs.writeFileSync(path.join(artifact,'main-ui.json'),JSON.stringify(state,null,2));
  console.log('MAIN_UI',JSON.stringify(state));
  // A tiny deterministic trusted SDK fixture exercises serialization/playback;
  // real model inference is covered independently by tests/model/.
  fs.copyFileSync(path.join(root,'tests/native_ui_media_fixture.py'),
    path.join(install,'extensions/Video/ssui_video/native_ui_media_fixture.py'));
  fs.writeFileSync(path.join(project,'workflow-media-smoke.py'),
    "from typing import Tuple\nfrom ssui import workflow, Video, Mesh\nfrom ssui.config import SSUIConfig\nfrom ssui_video.native_ui_media_fixture import make_assets\nconfig = SSUIConfig()\n@workflow\ndef generate_media() -> Tuple[Video, Mesh]:\n    if config.is_prepare():\n        return Video('mp4', [], fps=8), Mesh()\n    return make_assets()\n");
  // The workflow dialog is also opened through its normal UI action below.
  await clickText('Start from Preset Workflow');
  await until(()=>evaluate("return document.querySelectorAll('.workflow-item').length").then(x=>x>=6));
  await clickText('视频生成工作流','.workflow-item');
  await clickText('3D 模型生成','.workflow-item');
  await clickText('动作生成','.workflow-item');
  await evaluate(`return Array.from(document.querySelectorAll('input')).map(x=>({placeholder:x.placeholder,value:x.value}))`).then(x=>console.log('WORKFLOW_INPUTS',JSON.stringify(x)));
  fs.writeFileSync(path.join(artifact,'workflow-ui.txt'),await evaluate('return document.body.innerText'));
  await setInput('input[placeholder="Select workflow save location..."]',project);
  await clickText('Confirm');
  await until(()=>Promise.resolve(fs.existsSync(path.join(project,'workflow-wan21.py'))));
  for (const file of ['workflow-wan21.py','workflow-cogvideo2b.py','workflow-text-to-3d.py','workflow-motion.py','ssproject.yaml']) {
    assert.ok(fs.existsSync(path.join(project,file)),file);
  }
  const body=await until(()=>evaluate('return document.body.innerText').then(x=>x.includes('workflow-wan21.py') ? x : false));
  fs.writeFileSync(path.join(artifact,'workflow-created-ui.txt'),body);
  for (const file of ['workflow-wan21.py','workflow-cogvideo2b.py','workflow-text-to-3d.py','workflow-motion.py']) {
    const url='http://127.0.0.1:7422/api/script?'+new URLSearchParams({script_path:path.join(project,file)});
    const metadata=await fetch(url,{signal:AbortSignal.timeout(60000)}).then(x=>x.json());
    fs.writeFileSync(path.join(artifact,file+'.metadata.json'),JSON.stringify(metadata,null,2));
    assert.ok(!metadata.functions?.error,JSON.stringify(metadata));
    assert.ok(Object.keys(metadata.functions || {}).length>0,JSON.stringify(metadata));
  }
  console.log('DESKTOP_WORKFLOW_COPY_AND_SDK_DISCOVERY_PASS');
  await clickText('workflow-media-smoke.py','.bp5-tree-node-label');
  const iframe=await until(()=>request('/session/'+session+'/elements',
    {using:'css selector',value:'iframe'}).then(items=>items[0]));
  await request('/session/'+session+'/frame',{id:iframe});
  await until(()=>evaluate("return Array.from(document.querySelectorAll('button')).some(x=>['Run','运行'].includes(x.innerText.trim()))"));
  await clickText('GLBPreview', '[role="tab"]');
  await clickText('Run');
  await until(()=>evaluate("return document.querySelector('video')?.getAttribute('src') && document.querySelector('model-viewer')?.getAttribute('src')"),90000);
  const playback=await request('/session/'+session+'/execute/async',{script:"const done=arguments[arguments.length-1];const video=document.querySelector('video');video.muted=true;video.play().then(()=>done('playing')).catch(e=>done({error:e.message}));",args:[]});
  assert.equal(playback,'playing',JSON.stringify(playback));
  const media=await until(()=>evaluate("const video=document.querySelector('video');const model=document.querySelector('model-viewer');model?.scrollIntoView(); return video?.readyState>=2 && model?.loaded ? {videoWidth:video.videoWidth,duration:video.duration,controls:video.controls,meshLoaded:model.loaded} : false"),90000);
  assert.equal(media.videoWidth,32);assert.ok(media.duration>1);assert.equal(media.controls,true);
  fs.writeFileSync(path.join(artifact,'media-preview.json'),JSON.stringify(media,null,2));
  console.log('DESKTOP_VIDEO_AND_GLB_PREVIEW_PASS',JSON.stringify(media));
  const fixturePath=path.join(project,'workflow-media-smoke.py');
  const original=fs.readFileSync(fixturePath,'utf8');
  try {
    fs.writeFileSync(fixturePath,original.replace('return make_assets()',"raise ValueError('native smoke failure')"));
    await clickText('Run');
    await until(()=>evaluate("return document.body.innerText.includes('native smoke failure')"),30000);
    console.log('DESKTOP_EXECUTION_ERROR_FEEDBACK_PASS');
  } finally {fs.writeFileSync(fixturePath,original);}
  await request('/session/'+session+'/frame',{id:null});
  await clickText('workflow-wan21.py','.bp5-tree-node-label');
  const wanFrame=await until(()=>request('/session/'+session+'/elements',
    {using:'css selector',value:'iframe[src*="workflow-wan21.py"]'}).then(items=>items[0]));
  await request('/session/'+session+'/frame',{id:wanFrame});
  await until(()=>evaluate("return !!document.querySelector('input[placeholder=\"Model folder\"]')"));
  console.log('DESKTOP_MODEL_INPUT_BINDING_PASS');
  if(process.env.SSUI_WAN_MODEL_DIR) {
    await setInput('input[placeholder="Model folder"]',process.env.SSUI_WAN_MODEL_DIR);
    await evaluate("const area=document.querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(area,'A red toy car driving on a wooden table, cinematic lighting');area.dispatchEvent(new Event('input',{bubbles:true}));");
    await clickText('Run');
    await until(()=>evaluate("const error=document.querySelector('.bp5-callout-danger');if(error)throw Error(error.innerText);return document.querySelector('video')?.videoWidth===256"),180000);
    console.log('DESKTOP_REAL_WAN_INFERENCE_PASS');
  }
  console.log('DESKTOP_NATIVE_UI_PASS');
})().catch(async error=>{console.error(error);try{fs.writeFileSync(path.join(artifact,'failure-ui.html'),await evaluate('return document.documentElement.outerHTML'));}catch{}process.exitCode=1}).finally(stop);
