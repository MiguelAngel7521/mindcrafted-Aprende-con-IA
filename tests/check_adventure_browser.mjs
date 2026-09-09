// Recorrido real: teclado, estaciones, ocho mecánicas y jefe; no modifica el estado del motor.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const base=process.env.PRACTICE_TEST_URL||'http://127.0.0.1:8022';
const cdp=process.env.PIXEL_CDP_URL||'http://127.0.0.1:9228';
const output='/tmp/mindcrafted-adventure-check';await fs.mkdir(output+'/previews',{recursive:true});
const target=await(await fetch(cdp+'/json/new?about:blank',{method:'PUT'})).json();
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{socket.onopen=r;socket.onerror=j;});
let seq=0;const pending=new Map(),errors=[];
socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);else if(m.method==='Network.responseReceived'&&m.params.response.status>=400)errors.push(m.params.response.url+' '+m.params.response.status);};
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>reject(Error('CDP timeout '+method)),45000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function waitFor(expression){for(let i=0;i<180;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100));}throw Error('Not ready: '+expression);}
async function api(route,body,headers){const r=await fetch(base+route,{method:body===undefined?'GET':'POST',headers:headers||{'Content-Type':'application/json'},body:body===undefined?undefined:headers?body:JSON.stringify(body)});assert.equal(r.status,200,await r.clone().text());return r.json();}
async function screenshot(name){const {data}=await call('Page.captureScreenshot',{format:'png'});await fs.writeFile(output+'/previews/'+name+'.png',Buffer.from(data,'base64'));}
async function prepareDriver(cfg){await evaluate(`window.testConfig=${JSON.stringify(cfg)};window.testWalk=async function(goal,arena=false){
  const canvas=document.getElementById('world'),C=AdventureCore;
  const pos=()=>({x:Number(canvas.dataset.playerX),y:Number(canvas.dataset.playerY)});
  const boxes=arena?[]:testConfig.pixelWorld.map.layers.find(l=>l.name==='Colisiones').objects;
   const bounds=arena?{left:24,right:744,top:155,bottom:485}:testConfig.adventure.layout.bounds;
    const safe=point=>C.walkable(point,boxes,bounds)&&(arena||[-16,-8,0,8,16].every(dx=>[-16,-8,0,8,16].every(dy=>C.walkable({x:point.x+dx,y:point.y+dy},boxes,bounds))));
    await new Promise(requestAnimationFrame);
    const start=pos(),grid={x:Math.round(start.x/8)*8,y:Math.round(start.y/8)*8};
   const queue=[grid],parents=new Map([[grid.x+','+grid.y,null]]);let found;
   for(let n=0;n<queue.length;n++){const p=queue[n],key=p.x+','+p.y;if(C.distance(p,goal)<18){found=key;break;}
      for(const [dx,dy] of [[8,0],[-8,0],[0,8],[0,-8]]){const q={x:p.x+dx,y:p.y+dy},k=q.x+','+q.y;if(!parents.has(k)&&safe(q)){parents.set(k,key);queue.push(q);}}
   }
    if(!found)throw Error('No reachable test path '+JSON.stringify(goal));
   const path=[];while(found){const [x,y]=found.split(',').map(Number);path.unshift({x,y});found=parents.get(found);}
    const press=(key,down)=>window.dispatchEvent(new KeyboardEvent(down?'keydown':'keyup',{key,bubbles:true}));
    document.getElementById('stage').focus();const started=performance.now();
    for(let i=1;i<path.length;i++){
      const previous=path[i-1],point=path[i],axis=previous.x!==point.x?'x':'y',direction=point[axis]>previous[axis]?1:-1;
      let held;while((point[axis]-pos()[axis])*direction>0){if(performance.now()-started>30000)throw Error('Walk blocked '+JSON.stringify({point,pos:pos()}));const key=axis==='x'?(direction>0?'ArrowRight':'ArrowLeft'):(direction>0?'ArrowDown':'ArrowUp');if(held!==key){if(held)press(held,false);press(key,true);held=key;}await new Promise(requestAnimationFrame);}if(held)press(held,false);
    }
   await new Promise(requestAnimationFrame);return pos();
 };`);}
async function walk(goal,arena=false){return evaluate(`testWalk(${JSON.stringify(goal)},${arena})`);}
 async function activate(id){const point=await evaluate(`(()=>{const b=[...document.querySelectorAll('.target')].find(b=>b.dataset.target===${JSON.stringify(String(id))});if(!b)throw Error('Target absent '+${JSON.stringify(String(id))}+'; choices='+[...document.querySelectorAll('.target')].map(x=>x.dataset.target).join(','));return {x:parseFloat(b.style.left)*768/100,y:parseFloat(b.style.top)*512/100};})()`);await walk(point,true);await evaluate("document.getElementById('interact').click()");}
function solution(p){const d=p.data;return ({packet_route:()=>[1,2],algorithm_trace:()=>d.states,concept_links:()=>d.pairs.map((_,i)=>i),process_order:()=>d.steps.map((_,i)=>i),evidence_choice:()=>[d.answer],fraction_fill:()=>[...Array(d.numerator).fill('add'),'submit'],circuit_target:()=>[...Array(Math.floor(d.target_voltage/6)).fill('boost'),...Array(d.target_voltage%6).fill('up'),'submit'],balance_equation:()=>['cancel','divide','submit']})[p.kind]();}
async function solve(p){for(const answer of solution(p))await activate(answer);assert.equal(await evaluate("document.getElementById('stage').dataset.mode"),'result',p.kind);}
try{
  const upload=await api('/api/import-pptx?filename=expedicion.pptx',await fs.readFile(output+'/expedicion.pptx'),{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'});
  const content=await api('/api/parse-md-text',{markdown:upload.markdown});assert.equal(content.chunks.length,4);content.course.difficulty='study';
  const job=await api('/api/generate',{content,course_id:'adventure-'+Date.now()});let status;
  for(let i=0;i<100;i++){status=await api('/api/jobs/'+job.job_id);if(['failed','completed'].includes(status.status))break;await new Promise(r=>setTimeout(r,100));}
  assert.equal(status.status,'completed',JSON.stringify(status));assert.equal(status.result.boss_status,'ready');
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  const kinds=new Set();
  for(let room=0;room<4;room++){
    const chunk=content.chunks[room].id,pkg=await api('/api/play/'+job.course_id+'/'+chunk+'/package'),cfg=pkg.config;
    assert.equal(cfg.generationMode,'aventura');assert.equal(!!cfg.boss,room===3);
    await call('Page.navigate',{url:base+'/play?course='+job.course_id+'&game='+chunk});await waitFor("document.getElementById('stage')?.dataset.mode==='explore'");await prepareDriver(cfg);await screenshot('world-'+cfg.practice.world);
    for(let i=0;i<cfg.practice.puzzles.length;i++){
       const p=cfg.practice.puzzles[i],station=cfg.adventure.layout.stations[i];kinds.add(p.kind);
       await walk(station);await evaluate("document.getElementById('interact').click()");assert.equal(await evaluate("document.getElementById('stage').dataset.mode"),'read');
      await evaluate("document.querySelector('#dialog-actions button').click()");assert.equal(await evaluate("document.getElementById('stage').dataset.mode"),'arena');
      if(room===0&&i===0){
        await screenshot('network-encounter');
        await evaluate("document.getElementById('pause').click()");
        const before=await evaluate("document.getElementById('world').dataset.playerX");await new Promise(r=>setTimeout(r,200));assert.equal(await evaluate("document.getElementById('world').dataset.playerX"),before);
        await evaluate("document.querySelector('#dialog-actions button').click()");
        const mastery=await evaluate("document.getElementById('mastery').textContent");
        await evaluate("document.getElementById('difficulty').value='normal';document.getElementById('difficulty').dispatchEvent(new Event('change'))");
        await waitFor("document.getElementById('stage').dataset.mode==='defeat'");
        assert.equal(await evaluate("document.getElementById('mastery').textContent"),mastery,'Reflex failure altered knowledge');
        await evaluate("document.getElementById('difficulty').value='study';document.getElementById('difficulty').dispatchEvent(new Event('change'));document.querySelector('#dialog-actions button').click()");
        // An impossible connection is an educational error and must not solve the mission.
        await activate(2);assert.equal(await evaluate("document.getElementById('stage').dataset.mode"),'arena');
      }
      await solve(p);await evaluate("document.querySelector('#dialog-actions button').click()");
      console.log('Resuelto:',cfg.practice.world,p.kind);
    }
    assert.equal(await evaluate("document.getElementById('progress').textContent"),'3 / 3');
    await call('Page.reload');await waitFor("document.getElementById('stage')?.dataset.mode==='explore'");assert.equal(await evaluate("document.getElementById('progress').textContent"),'3 / 3');await prepareDriver(cfg);
    if(cfg.boss){
      await walk(cfg.adventure.layout.exit);await evaluate("document.getElementById('interact').click();document.querySelector('#dialog-actions button').click();document.querySelector('#dialog-actions button').click()");
      await screenshot('boss-final');
      for(let phase=0;phase<3;phase++){
        await solve(cfg.boss.phases[phase]);await evaluate("document.querySelector('#dialog-actions button').click()");
        if(phase<2)await evaluate("document.querySelector('#dialog-actions button').click()");
        console.log('Jefe: fase',phase+1,'superada');
      }
      assert.equal(await evaluate("document.getElementById('completion').hidden"),false);
      assert.ok(await evaluate("document.getElementById('completion-copy').textContent.includes('tres fases')"));
    }
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
    assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,'Mobile overflow');await screenshot('mobile-'+cfg.practice.world);
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:base+'/courses/'+job.course_id+'/games/'+chunk+'/'});await waitFor("document.getElementById('adventure-data') && document.getElementById('stage')?.dataset.mode==='explore'");assert.equal(await evaluate("document.getElementById('progress').textContent"),'3 / 3');
  }
  assert.equal(kinds.size,8);assert.deepEqual(errors,[]);
  console.log('OK: PPTX, cuatro mundos recorridos, ocho mecánicas, pausa, derrota sin penalización educativa, guardado, móvil, HTML exportado y victoria contra el jefe. IA simulada.');
}finally{socket.close();await fetch(cdp+'/json/close/'+target.id);}
