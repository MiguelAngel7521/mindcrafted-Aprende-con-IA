// Prueba la vista real con Chromium DevTools; Node >=22, sin paquetes npm.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root='/tmp/mindcrafted-practice-check';
await fs.mkdir(root+'/previews',{recursive:true});
const endpoint=process.env.PIXEL_CDP_URL||'http://127.0.0.1:9228';
const base=process.env.PRACTICE_TEST_URL||'http://127.0.0.1:8022';
const target=await (await fetch(endpoint+'/json/new?about:blank',{method:'PUT'})).json();
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let seq=0;const pending=new Map(),errors=[];
socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=pending.get(message.id);if(item){clearTimeout(item.timer);pending.delete(message.id);message.error?item.reject(new Error(JSON.stringify(message.error))):item.resolve(message.result);}}else if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.text);else if(message.method==='Network.responseReceived'&&message.params.response.status>=400)errors.push(message.params.response.url+' '+message.params.response.status);};
const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});
async function evaluate(expression){const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
async function waitFor(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100));}throw new Error('No se cumplió: '+expression);}
async function screenshot(name){const {data}=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(root,'previews',name+'.png'),Buffer.from(data,'base64'));}
async function api(route,body,headers){const response=await fetch(base+route,{method:body===undefined?'GET':'POST',headers:headers||{'Content-Type':'application/json'},body:body===undefined?undefined:headers?body:JSON.stringify(body)});assert.equal(response.status,200,route+': '+await response.clone().text());return response.json();}
try{
  const upload=await api('/api/import-pptx?filename=apuntes.pptx',await fs.readFile(root+'/apuntes.pptx'),{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'});
  assert.ok(upload.markdown.includes('ley de Ohm'));
  const content=await api('/api/parse-md-text',{markdown:upload.markdown});
  assert.equal(content.chunks.length,3);
  content.course.gameplay='practica'; // Verify previous packages still use their original player.
  content.chunks.forEach((c,i)=>c.id=['chunk-2','chunk-10','botanica'][i]);
  content.chunks.splice(1,0,{id:'fallo',title:'Material insuficiente',content:'material insuficiente '.repeat(5)});
  const job=await api('/api/generate',{content,course_id:'browser-'+Date.now()});
  let final;
  for(let i=0;i<100;i++){final=await api('/api/jobs/'+job.job_id);if(['completed','failed'].includes(final.status))break;await new Promise(r=>setTimeout(r,100));}
  assert.equal(final.status,'completed',JSON.stringify(final));assert.equal(final.result.partial,true);assert.equal(final.result.first_game,'chunk-2');
  assert.deepEqual(final.result.games.map(g=>g.status),['success','failed','success','success']);
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  const covered=new Set();
  for(const [chunk,world,next] of [['chunk-2','mathematics','chunk-10'],['chunk-10','laboratory','botanica'],['botanica','biology',null]]){
    const pkg=await api('/api/play/'+job.course_id+'/'+chunk+'/package'),plan=pkg.config.practice;
    assert.equal(plan.world,world);
    assert.equal(pkg.config.nextGameUrl,next?'/play?course='+job.course_id+'&game='+next:undefined);
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
    const url=base+'/play?course='+job.course_id+'&game='+chunk;
    await call('Page.navigate',{url});await waitFor("document.getElementById('practice-app') && !document.getElementById('practice-app').hidden");
    await evaluate('document.fonts.ready');await screenshot('practice-'+world);
    for(let i=0;i<plan.puzzles.length;i++){
      const p=plan.puzzles[i];covered.add(p.kind);
      await evaluate(`document.querySelectorAll('#puzzles button')[${i}].click();document.getElementById('check').click()`);
      assert.equal(await evaluate("document.getElementById('check').disabled"),false,'An unsolved puzzle was accepted: '+p.kind);
      await evaluate("document.getElementById('hint').click()");
      await evaluate(`(function(){const d=${JSON.stringify(p.data)};const host=document.getElementById('exercise');
        switch(${JSON.stringify(p.kind)}){
          case 'balance_equation':{
            const select=host.querySelector('select'),amount=host.querySelector('input'),apply=host.querySelector('button');
            if(d.b){select.value=d.b>0?'subtract':'add';amount.value=Math.abs(d.b);apply.click();}
            select.value='divide';amount.value=d.a;apply.click();break;
          }
          case 'fraction_fill': [...host.querySelectorAll('.fraction-pieces button')].slice(0,d.numerator).forEach(b=>b.click());break;
          case 'circuit_target':{const slider=host.querySelector('input');slider.value=d.target_voltage;slider.dispatchEvent(new Event('input'));break;}
          case 'concept_links': d.pairs.forEach((pair,i)=>{host.querySelectorAll('.link-column')[0].children[i].click();[...host.querySelectorAll('.link-column')[1].children].find(b=>b.textContent.slice(3)===pair.right).click();});break;
          case 'process_order': d.steps.forEach((step,target)=>{let rows=[...host.querySelectorAll('.sequence-row')];let pos=rows.findIndex(r=>r.firstChild.textContent.slice(3)===step);while(pos>target){rows[pos].querySelector('button').click();pos--;rows=[...host.querySelectorAll('.sequence-row')];}});break;
          case 'evidence_choice': [...host.querySelectorAll('.choices button')].find(b=>b.textContent===d.options[d.answer]).click();break;
        }
        document.getElementById('check').click();})()`);
      assert.equal(await evaluate("document.getElementById('check').disabled"),true,'Cannot solve '+p.kind);
    }
    assert.equal(await evaluate("document.getElementById('progress-count').textContent"),'3 / 3');
    assert.equal(await evaluate("document.getElementById('finished').hidden"),false);
    await call('Page.reload');await waitFor("document.getElementById('progress-count')?.textContent === '3 / 3'");
    await evaluate("document.querySelector('#puzzles button').click();document.getElementById('restart').click()");
    assert.equal(await evaluate("document.getElementById('check').disabled"),false);
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true,'Mobile overflow '+world);
    await screenshot('practice-'+world+'-mobile');
    await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
    await waitFor("document.getElementById('motion').getAttribute('aria-pressed') === 'true'");
    // Direct exported HTML exercises the self-contained package as well.
    await call('Page.navigate',{url:base+'/courses/'+job.course_id+'/games/'+chunk+'/'});
    await waitFor("document.getElementById('practice-data') && !document.getElementById('practice-app').hidden");
    assert.equal(await evaluate("document.getElementById('progress-count').textContent"),'3 / 3');
  }
  await call('Page.navigate',{url:base+'/'});
  await waitFor("typeof renderStructure === 'function' && window.__edgcServerCfg?.has_api_key");
  await evaluate(`_parsedContent=${JSON.stringify(content)};renderStructure(_parsedContent);startGeneration()`);
  await waitFor("document.getElementById('genResult').classList.contains('visible')");
  assert.ok(await evaluate("document.getElementById('genStatusText').textContent.includes('pendientes')"));
  assert.equal(await evaluate("document.querySelectorAll('#genGames a').length"),3);
  assert.equal(await evaluate("document.querySelector('#gc1 a') === null"),true);
  assert.equal(await evaluate("document.querySelector('#gc1 details p').textContent.includes('fieles')"),true);
  assert.ok(await evaluate("document.getElementById('genResultLink').href.endsWith('game=chunk-2')"));
  assert.equal(await evaluate("document.getElementById('genBtn').disabled"),false);
  assert.equal(covered.size,6);
  assert.deepEqual(errors,[]);
  console.log('OK: PPTX → Markdown → generación parcial → 3 mundos; seis mecánicas, rechazos, pistas, resolución, persistencia, HTML exportado, móvil, movimiento reducido y resultados reales en el estudio. IA simulada. Capturas: '+root+'/previews');
}finally{socket.close();await fetch(endpoint+'/json/close/'+target.id);}
