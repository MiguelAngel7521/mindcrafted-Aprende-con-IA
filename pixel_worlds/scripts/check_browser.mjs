// Prueba la vista real con Chromium DevTools; Node >=22, sin paquetes npm.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const endpoint=process.env.PIXEL_CDP_URL||'http://127.0.0.1:9228';
const base=process.env.PIXEL_PREVIEW_URL||'http://127.0.0.1:8011/web/';
const target=await (await fetch(endpoint+'/json/new?about:blank',{method:'PUT'})).json();
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let seq=0;const pending=new Map(),errors=[];
socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=pending.get(message.id);if(item){clearTimeout(item.timer);pending.delete(message.id);message.error?item.reject(new Error(JSON.stringify(message.error))):item.resolve(message.result);}}else if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.text);else if(message.method==='Network.responseReceived'&&message.params.response.status>=400)errors.push(message.params.response.url+' '+message.params.response.status);};
const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});
async function evaluate(expression){const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
async function waitFor(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100));}throw new Error('No se cumplió: '+expression);}
async function screenshot(name){const {data}=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(root,'previews',name+'.png'),Buffer.from(data,'base64'));}
try{
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1250,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:base});
  await waitFor("document.getElementById('current') && document.getElementById('loading').hidden");
  await evaluate("document.fonts.ready");
  assert.equal(await evaluate("document.querySelectorAll('.world-button').length"),3);
  await screenshot('atlas-desktop');
  await evaluate("document.getElementById('voltage').value=12; document.getElementById('voltage').dispatchEvent(new Event('input')); document.getElementById('resistance').value=6; document.getElementById('resistance').dispatchEvent(new Event('input'));");
  assert.equal(await evaluate("document.getElementById('current').textContent"),'2 A');
  await evaluate("document.getElementById('switch').click()");
  assert.equal(await evaluate("document.getElementById('current').textContent"),'0 A');
  await evaluate("document.querySelector('[data-world=mathematics]').click()");
  await waitFor("document.getElementById('equation-left') && document.getElementById('loading').hidden");
  await evaluate("document.getElementById('apply').click(); document.getElementById('operation').value='divide'; document.getElementById('amount').value=2; document.getElementById('apply').click()");
  assert.equal(await evaluate("document.getElementById('equation-left').textContent"),'x');
  assert.equal(await evaluate("document.getElementById('equation-right').textContent"),'5');
  await evaluate("document.querySelector('[data-world=biology]').click()");
  await waitFor("document.getElementById('water') && document.getElementById('loading').hidden");
  await evaluate("for(const id of ['water','pollinators']){const input=document.getElementById(id);input.value=80;input.dispatchEvent(new Event('input'));}");
  assert.equal(await evaluate("document.getElementById('reproduction').textContent"),'80');
  await evaluate("document.querySelectorAll('#hotspots button')[1].click()");
  assert.equal(await evaluate("document.getElementById('inspection').hidden"),false);
  await evaluate("document.getElementById('close-inspection').click();scrollTo(0,0)");
  await screenshot('atlas-biology');
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate('scrollTo(0,0)');
  await screenshot('atlas-mobile');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'),true,'Desbordamiento horizontal en móvil');
  await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await waitFor("document.getElementById('motion').getAttribute('aria-pressed') === 'true'");
  assert.equal(await evaluate("document.getElementById('motion').getAttribute('aria-pressed')"),'true');
  assert.deepEqual(errors,[]);
  console.log('OK: carga, 3 mundos, circuito, ecuación, ecosistema, notas, móvil y movimiento reducido. Sin errores de JavaScript ni HTTP.');
}finally{socket.close();await fetch(endpoint+'/json/close/'+target.id);}
