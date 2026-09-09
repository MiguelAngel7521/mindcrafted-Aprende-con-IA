(function(){
'use strict';
const $=id=>document.getElementById(id),C=window.AdventureCore,E=window.AdventureEncounters;
const canvas=$('world'),ctx=canvas.getContext('2d'),keys=new Set();
const media=matchMedia('(prefers-reduced-motion: reduce)');
let config,plan,world,images={},saveKey,state,tracker,boxes,bounds,player,mode='loading',pausedFrom;
let selected=0,activePuzzle,encounter,isBoss=false,bossPhase=0,hp=5,remaining=12,elapsed=0,invulnerable=0;
let shots=[],targets=[],random,spawnAt=0,last=0,visualTime=0,moving=false,errors=0,hints=0,lastSave=0,banner='',audioContext;
const difficulty=()=>$('difficulty').value;
const duration=()=>difficulty()==='calm'?22:14;
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function button(text,fn,cls){const b=node('button',text,cls);b.type='button';b.onclick=fn;return b;}
function say(text){banner=text;$('feedback').textContent=text;}
function sound(win){if(!$('sound').checked)return;try{audioContext=audioContext||new (window.AudioContext||window.webkitAudioContext)();audioContext.resume();const osc=audioContext.createOscillator(),gain=audioContext.createGain();osc.type='triangle';osc.frequency.value=win?660:220;gain.gain.setValueAtTime(.035,audioContext.currentTime);gain.gain.exponentialRampToValueAtTime(.001,audioContext.currentTime+.15);osc.connect(gain);gain.connect(audioContext.destination);osc.start();osc.stop(audioContext.currentTime+.16);}catch(_){}}
function save(){try{localStorage.setItem(saveKey,JSON.stringify(state));}catch(_){say('El navegador no permite guardar la partida. Puedes seguir jugando durante esta sesión.');}}
function worldDone(){return plan.puzzles.every(p=>state.done[p.id]?.complete);}
function routeDone(){return (config.courseRoute||[]).every(r=>{
  if(r.chunkId===config.chunkId)return worldDone();
  try{const s=JSON.parse(localStorage.getItem('mindcrafted_adventure_v1:'+config.courseId+':'+r.chunkId+':'+r.hash)||'{}');return r.puzzleIds.every(id=>s.done?.[id]?.complete===true);}catch(_){return false;}
});}
function setMode(value){mode=value;$('stage').dataset.mode=value;keys.clear();$('arena-hud').hidden=value!=='arena';$('arena-prompt').hidden=value!=='arena';$('targets').hidden=value!=='arena';$('mode-label').textContent=value==='arena'?(isBoss?'JEFE · FASE '+(bossPhase+1):'ENCUENTRO'):value==='explore'?'EXPLORACIÓN':'PAUSA DE LECTURA';}
function dialog(kicker,title,copy,actions,evidence=''){
  $('overlay').hidden=false;$('dialog-kicker').textContent=kicker;$('dialog-title').textContent=title;$('dialog-copy').textContent=copy;
  $('evidence').textContent=evidence;$('evidence-details').hidden=!evidence;$('evidence-details').open=false;
  $('dialog-actions').replaceChildren(...actions.map((a,i)=>button(a[0],a[1],i===0?'primary':'')));
  $('dialog-actions').firstChild?.focus();
}
function closeDialog(){ $('overlay').hidden=true;$('stage').focus();}
function resumeWorld(){closeDialog();setMode('explore');player={...state.position,direction:0};update();}
function progress(){return plan.puzzles.filter(p=>state.done[p.id]?.complete).length;}
function update(){
  $('progress').textContent=progress()+' / '+plan.puzzles.length;
  $('mastery').textContent='Dominio estimado: '+Math.round(tracker.summary().mastery*100)+'%';
  $('missions').replaceChildren(...plan.puzzles.map((p,i)=>button((state.done[p.id]?.complete?'✓ ':String(i+1)+'. ')+p.title,()=>{selected=i;say('Busca la estación '+(i+1)+' en el mapa: '+p.title);update();},(state.done[p.id]?.complete?'done ':'')+(selected===i?'selected':''))));
  $('objective').textContent=worldDone()?'Las estaciones están restauradas. Acércate al portal del norte para continuar.':'Misión actual: '+plan.puzzles[selected].title+'. Acércate al marcador iluminado y pulsa E.';
  $('course-route').replaceChildren(...(config.courseRoute||[]).map(r=>{const a=node('a',r.title+(r.chunkId===config.chunkId?' · aquí':''));a.href='/play?course='+encodeURIComponent(config.courseId)+'&game='+encodeURIComponent(r.chunkId);return a;}));
  const complete=worldDone()&&(!config.boss||state.bossWon);
  $('completion').hidden=!complete;
  $('completion-title').textContent=state.bossWon?'El guardián reconoce tu conocimiento.':'Sector restaurado.';
  $('completion-copy').textContent=(config.boss?.partial?'Has completado la parte disponible del curso. Hay lecciones pendientes de generación. ':'')+(state.bossWon?'Has superado las tres fases. ':'')+plan.puzzles.map(p=>p.concept+': '+(state.done[p.id]?.score||0)+' puntos').join(' · ');
  $('next').href=config.nextGameUrl||$('back').href;$('next').textContent=config.nextGameUrl?'Siguiente sector →':'Volver al curso →';
}
function nearStation(){const stations=config.adventure.layout.stations;return stations.map((s,i)=>({s,i,d:C.distance(player,s)})).filter(x=>x.d<34).sort((a,b)=>a.d-b.d)[0];}
function openMission(i){
  selected=i;activePuzzle=plan.puzzles[i];isBoss=false;errors=0;hints=0;state.position={x:player.x,y:player.y};save();setMode('read');
  dialog('ESTACIÓN '+(i+1)+(state.done[activePuzzle.id]?.complete?' · RESTAURADA':''),activePuzzle.title,activePuzzle.instruction+' Durante la acción, acércate a una respuesta numerada y pulsa E para activarla. Las zonas de respuesta protegen de los proyectiles.',[
    ['Entrar al reto',()=>startEncounter(false)],['Volver al mapa',resumeWorld]
  ],activePuzzle.evidence);
}
function openExit(){
  if(!worldDone()){say('Restaura las estaciones de este sector para abrir el portal.');return;}
  if(!config.boss){if(config.nextGameUrl)location.href=config.nextGameUrl;else location.href=$('back').href;return;}
  state.position={x:player.x,y:player.y};save();setMode('read');
  if(config.boss.status!=='ready'){dialog('CIERRE PENDIENTE','El guardián aún no está listo',config.boss.error||'El cierre necesita volver a generarse.',[['Volver al mapa',resumeWorld]]);return;}
  if(!routeDone()){dialog('PORTAL CERRADO','Completa los sectores anteriores','El guardián combina lo practicado en las lecciones disponibles. Usa la lista de sectores para completar sus estaciones.',[['Volver al mapa',resumeWorld]]);return;}
  bossPhase=0;isBoss=true;errors=0;hints=0;activePuzzle=config.boss.phases[0];
  dialog(config.boss.partial?'JEFE DE LA PARTE DISPONIBLE':'JEFE FINAL',config.boss.name,'Tres fases para recuperar el núcleo. Cada solución correcta rompe un segmento del escudo. Al perder puedes reintentar sin borrar tus estaciones.',[['Enfrentar al guardián',prepareBoss],['Volver al mapa',resumeWorld]]);
}
function prepareBoss(){activePuzzle=config.boss.phases[bossPhase];setMode('read');dialog('FASE '+(bossPhase+1)+' / 3 · '+activePuzzle.originTitle,activePuzzle.title,activePuzzle.instruction,[['Comenzar fase',()=>startEncounter(true)],['Volver al mapa',resumeWorld]],activePuzzle.evidence);}
function refreshTargets(){
  const view=encounter.view();$('arena-prompt').textContent=view.prompt;
  const shuffled=view.choices.slice();for(let i=shuffled.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[shuffled[i],shuffled[j]]=[shuffled[j],shuffled[i]];}
  const positions=[[128,190],[384,190],[640,190],[128,432],[384,432],[640,432]];
  targets=shuffled.map((choice,i)=>({...choice,x:positions[i][0],y:positions[i][1],number:i+1}));
  $('targets').replaceChildren(...targets.map(t=>{const b=button(t.number+'. '+t.label,()=>{if(mode==='arena'&&C.distance(player,t)<44)activate(t);else say('Acércate a la zona '+t.number+' para activar esa respuesta.');},'target');b.style.left=t.x/768*100+'%';b.style.top=t.y/512*100+'%';b.dataset.target=String(t.id);return b;}));
}
function startEncounter(boss){
  isBoss=boss;hp=5;remaining=duration();elapsed=0;invulnerable=0;shots=[];spawnAt=1.5;
  random=C.random(config.adventure.seed+selected*137+(boss?1009+bossPhase:0));encounter=E.create(activePuzzle);
  player={x:384,y:330,direction:0};closeDialog();setMode('arena');refreshTargets();say('Acércate a una zona y pulsa E. Esquivar no cuenta como respuesta.');
}
function activate(target){
  const result=encounter.act(target.id);
  if(result.assessed&&!result.correct){errors++;tracker.observe(activePuzzle.skillId,false,{label:activePuzzle.concept,score:0});sound(false);say('Revisa la relación: '+activePuzzle.hint);}
  if(result.done){
    const score=Math.max(40,100-errors*10-hints*5);tracker.observe(activePuzzle.skillId,true,{label:activePuzzle.concept,score});sound(true);
    if(!isBoss){state.done[activePuzzle.id]={complete:true,score:Math.max(score,state.done[activePuzzle.id]?.score||0)};save();}
    setMode('result');
    if(isBoss){bossPhase++;if(bossPhase===3){state.bossWon=true;save();dialog('VICTORIA',config.boss.name+' ha sido superado.',activePuzzle.explanation+' Has conectado los conceptos de las tres fases.',[['Volver al mundo',resumeWorld]],activePuzzle.evidence);}else dialog('ESCUDO REDUCIDO','Fase superada',activePuzzle.explanation,[['Siguiente fase',prepareBoss],['Volver al mapa',resumeWorld]],activePuzzle.evidence);}
    else dialog('ESTACIÓN RESTAURADA',activePuzzle.title,activePuzzle.explanation+' La estación vuelve a estar activa.',[['Volver al mundo',resumeWorld],['Repetir reto',()=>startEncounter(false)]],activePuzzle.evidence);
    update();return;
  }
  // A completed educational step starts a fresh window; moving controls also give time.
  remaining=duration();if(result.advanced){sound(true);say('Conexión correcta. Continúa con el siguiente paso.');}
  refreshTargets();update();
}
function interact(){
  if(mode==='explore'){if(C.distance(player,config.adventure.layout.exit)<38)openExit();else{const n=nearStation();if(n)openMission(n.i);else say('Acércate a una estación o al portal del norte.');}}
  else if(mode==='arena'){const near=targets.filter(t=>C.distance(player,t)<44).sort((a,b)=>C.distance(player,a)-C.distance(player,b))[0];if(near)activate(near);else say('Necesitas estar junto a una respuesta para confirmarla.');}
}
$('interact').onclick=interact;
function pause(){
  if(mode==='paused'){const previous=pausedFrom;closeDialog();setMode(previous);return;}
  if(!['explore','arena'].includes(mode))return;
  pausedFrom=mode;setMode('paused');dialog('PAUSA','Respira. Tu partida espera.','El movimiento, los proyectiles y el tiempo están detenidos.',[['Continuar',pause],['Volver al mapa',resumeWorld]]);
}
$('pause').onclick=pause;
$('hint').onclick=()=>{
  const puzzle=activePuzzle&&mode==='arena'?activePuzzle:plan.puzzles[selected];
  if(mode==='arena'){hints++;pause();$('dialog-copy').textContent=puzzle.hint;$('evidence-details').hidden=false;$('evidence').textContent=puzzle.evidence;}else say(puzzle.hint);
};
$('difficulty').onchange=()=>{remaining=duration();shots=[];say('Ritmo: '+$('difficulty').selectedOptions[0].textContent);};
function keyDirection(){return [Number(keys.has('right')||keys.has('d')||keys.has('arrowright'))-Number(keys.has('left')||keys.has('a')||keys.has('arrowleft')),Number(keys.has('down')||keys.has('s')||keys.has('arrowdown'))-Number(keys.has('up')||keys.has('w')||keys.has('arrowup'))];}
window.addEventListener('keydown',event=>{
  if(['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;
  const k=event.key.toLowerCase();if(k==='escape'){event.preventDefault();if(!event.repeat)pause();return;}
  if(!['explore','arena'].includes(mode))return;
  // Buttons retain native Enter behavior when focused, avoiding two confirmations.
  if(event.target.tagName==='BUTTON'&&k==='enter')return;
  if(['w','a','s','d','arrowup','arrowleft','arrowdown','arrowright','e','enter',' '].includes(k)){event.preventDefault();if(['e','enter',' '].includes(k)){if(!event.repeat)interact();}else keys.add(k);}
});
window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
window.addEventListener('blur',()=>{keys.clear();if(['explore','arena'].includes(mode))pause();});
document.addEventListener('visibilitychange',()=>{if(document.hidden){keys.clear();if(['explore','arena'].includes(mode))pause();}});
for(const b of document.querySelectorAll('[data-dir]')){
  b.onpointerdown=e=>{e.preventDefault();b.setPointerCapture(e.pointerId);keys.add(b.dataset.dir);};
  b.onpointerup=b.onpointercancel=b.onlostpointercapture=()=>keys.delete(b.dataset.dir);
}
function lose(timeout){setMode('defeat');sound(false);dialog(timeout?'VENTANA TERMINADA':'ENERGÍA AGOTADA',timeout?'Vuelve a intentarlo con calma.':'La expedición continúa.',
  'Tus estaciones y tu dominio de la materia se conservan. Puedes reducir el ritmo o activar Estudio sin presión.',[
    [isBoss?'Reintentar batalla':'Reintentar encuentro',()=>{if(isBoss){bossPhase=0;prepareBoss();}else startEncounter(false);}],['Volver al mapa',resumeWorld]
  ],activePuzzle.evidence);}
function simulate(dt){
  if(!['explore','arena'].includes(mode))return;
  const [dx,dy]=keyDirection();moving=C.move(player,dx,dy,dt,mode==='explore'?boxes:[],mode==='explore'?bounds:{left:24,right:744,top:155,bottom:485},mode==='arena'?225:165);
  if(mode==='explore'){
    state.position={x:player.x,y:player.y};if(visualTime-lastSave>1){save();lastSave=visualTime;}
    const n=nearStation(),atExit=C.distance(player,config.adventure.layout.exit)<38;
    $('interaction').textContent=atExit?(worldDone()?'Portal del norte · continuar':'Portal cerrado · faltan estaciones'):n?'E · '+n.s.title:'WASD / flechas · Busca una estación iluminada.';
    return;
  }
  elapsed+=dt;invulnerable=Math.max(0,invulnerable-dt);
  if(difficulty()!=='study')remaining-=dt;
  if(remaining<=0){lose(true);return;}
  const protectedZone=targets.some(t=>C.distance(t,player)<43);
  if(elapsed>=spawnAt&&difficulty()!=='study'){
    const count=difficulty()==='calm'?3:6,pattern=isBoss?config.boss.pattern:['rain','cross','wave'][selected%3];
    for(let i=0;i<count;i++){
      const x=40+random()*680,speed=difficulty()==='calm'?70:110+bossPhase*12;
      shots.push(pattern==='cross'?{x:i%2?748:20,y:245+random()*135,vx:i%2?-speed:speed,vy:0}:pattern==='wave'?{x,y:225,vx:Math.sin(elapsed+i)*35,vy:speed}:{x,y:220,vx:0,vy:speed});
    }
    spawnAt=elapsed+(difficulty()==='calm'?2.4:1.3);
  }
  for(const s of shots){s.x+=s.vx*dt;s.y+=s.vy*dt;if(!protectedZone&&invulnerable<=0&&C.distance(s,player)<12){hp--;invulnerable=1;sound(false);if(hp<=0){lose(false);return;}}}
  shots=shots.filter(s=>s.x>-10&&s.x<778&&s.y<522&&s.y>0).slice(-80);
  $('health').textContent='ENERGÍA '+'◆'.repeat(hp)+'◇'.repeat(5-hp);$('timer').textContent=difficulty()==='study'?'SIN PRESIÓN':Math.ceil(remaining)+' s';$('shield').textContent=isBoss?'ESCUDO '+(3-bossPhase)+'/3':'SEÑAL ACTIVA';
  let nearest=null;targets.forEach((t,i)=>{const near=C.distance(player,t)<44;$('targets').children[i]?.classList.toggle('near',near);if(near)nearest=t;});
  $('interaction').textContent=nearest?'E · '+nearest.label:'Desplázate a una zona numerada y confirma con E.';
}
function sprite(asset,x,y,w,h,frame=0){const a=world.assets[asset],img=images[asset];if(!a||!img)return;ctx.drawImage(img,(frame%a.frames)*a.width,0,a.width,a.height,x,y,w,h);}
function drawPlayer(){const frame=(player.direction||0)*4+(moving?Math.floor(visualTime*8)%4:0);ctx.globalAlpha=invulnerable>0&&$('effects').checked?.6:1;sprite('adventure-explorer',player.x-16,player.y-43,32,48,frame);ctx.globalAlpha=1;}
function draw(){
  if(!world||!player)return;
  canvas.dataset.playerX=player.x.toFixed(1);canvas.dataset.playerY=player.y.toFixed(1);
  ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,768,512);
  const arena=['arena','defeat','result'].includes(mode)||(mode==='paused'&&pausedFrom==='arena');
  if(arena){
    ctx.fillStyle='#0d1727';ctx.fillRect(0,0,768,512);ctx.strokeStyle='#20354a';
    for(let x=0;x<768;x+=32){ctx.beginPath();ctx.moveTo(x,145);ctx.lineTo(x,512);ctx.stroke();}
    for(let y=145;y<512;y+=32){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(768,y);ctx.stroke();}
    ctx.strokeStyle=world.accent;ctx.lineWidth=2;ctx.strokeRect(18,148,732,346);
    if(isBoss){sprite(config.boss.sprite,352,235,64,64,$('effects').checked?Math.floor(visualTime*6):0);ctx.fillStyle=['#72e2d2','#e8b977','#be90e9'][config.boss.crest];ctx.fillRect(379,226,10,7);}
    if(difficulty()!=='study'&&spawnAt-elapsed<.55){ctx.fillStyle='#e8b977';ctx.font='11px monospace';ctx.textAlign='center';ctx.fillText('↓ INTERFERENCIA ENTRANTE ↓',384,222);}
    targets.forEach(t=>{ctx.fillStyle=C.distance(player,t)<43?'#28565f':'#1c3548';ctx.fillRect(t.x-44,t.y-23,88,46);});
    ctx.fillStyle='#efb782';shots.forEach(s=>{ctx.fillRect(s.x-4,s.y-4,8,8);ctx.fillStyle='#f6edcb';ctx.fillRect(s.x-1,s.y-1,2,2);ctx.fillStyle='#efb782';});
    if(activePuzzle?.kind==='fraction_fill'){const v=encounter.view();for(let i=0;i<v.denominator;i++){ctx.fillStyle=i<v.charge?world.accent:'#314553';ctx.fillRect(270+i*18,253,14,14);}}
    drawPlayer();return;
  }
  const m=world.map,ground=m.layers.find(l=>l.name==='Suelo');
  ground.data.forEach((gid,i)=>{if(!gid)return;ctx.drawImage(images['terrain-'+world.id],(gid-1)%8*32,Math.floor((gid-1)/8)*32,32,32,i%m.width*32,Math.floor(i/m.width)*32,32,32);});
  const objects=m.layers.find(l=>l.name==='Escenario').objects.map(o=>({...o,asset:o.properties.find(p=>p.name==='asset_id').value}));
  objects.push({y:player.y,player:true});objects.sort((a,b)=>a.y-b.y);
  objects.forEach(o=>{if(o.player){drawPlayer();return;}const a=world.assets[o.asset];
    const assigned=config.adventure.layout.stations.filter(s=>s.asset===o.asset);
    const restored=assigned.some(s=>state.done[s.id]?.complete);
    sprite(o.asset,o.x,o.y-o.height,o.width,o.height,$('effects').checked&&(!assigned.length||restored)?Math.floor(visualTime*1000/a.frameDuration):0);
    if(restored){ctx.fillStyle='#65e5d1';ctx.fillRect(o.x+4,o.y-8,o.width-8,3);}
  });
  config.adventure.layout.stations.forEach((s,i)=>{
    const done=state.done[s.id]?.complete;ctx.fillStyle=done?'#69dfc4':i===selected?world.accent:'#c5a0de';
    ctx.fillRect(s.x-12,s.y-7,24,14);ctx.strokeStyle='#10232c';ctx.strokeRect(s.x-12,s.y-7,24,14);
    ctx.font='11px monospace';ctx.textAlign='center';ctx.fillStyle='#10232c';ctx.fillText(done?'✓':String(i+1),s.x,s.y+4);
    if(done){ctx.strokeStyle='#62d8c0';ctx.strokeRect(s.x-17,s.y-12,34,24);}
  });
  const exit=config.adventure.layout.exit;ctx.fillStyle=worldDone()?'#65e5d1':'#746584';ctx.fillRect(exit.x-22,exit.y-22,44,26);ctx.font='10px monospace';ctx.textAlign='center';ctx.fillStyle='#10232c';ctx.fillText(worldDone()?'PORTAL':'CERRADO',exit.x,exit.y-5);
}
function frame(time){const dt=Math.min(.05,Math.max(0,(time-last)/1000));last=time;if(['explore','arena'].includes(mode)){visualTime+=dt;simulate(dt);}draw();requestAnimationFrame(frame);}
(async()=>{try{
  const inline=$('adventure-data'),query=new URLSearchParams(location.search);let pkg;
  if(inline)pkg=JSON.parse(inline.textContent);else{const course=query.get('course'),game=query.get('game');if(!course||!game)throw new Error('Abre la aventura desde un curso.');const response=await fetch('/api/play/'+encodeURIComponent(course)+'/'+encodeURIComponent(game)+'/package');if(!response.ok)throw new Error('No se pudo abrir la aventura.');pkg=await response.json();}
  config=pkg.config;plan=config.practice;world=config.pixelWorld;if(config.adventure?.version!==1)throw new Error('Versión de aventura no compatible.');
  saveKey=C.storageKey(config);let raw;try{raw=JSON.parse(localStorage.getItem(saveKey)||'null');}catch(_){}
  state=C.restore(raw,config);boxes=world.map.layers.find(l=>l.name==='Colisiones').objects;bounds=config.adventure.layout.bounds;
  if(!C.walkable(state.position,boxes,bounds))state.position={...config.adventure.layout.spawn};player={...state.position,direction:0};
  tracker=window.MindCraftedBKT.createTracker({scope:config.courseId||config.sourceHash});
  images=Object.fromEntries(await Promise.all(Object.entries(world.assets).map(([id,a])=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve([id,i]);i.onerror=()=>reject(new Error('Falta el recurso '+id));i.src=a.image;}))));
  document.title=plan.title+' · Expedición';document.documentElement.style.setProperty('--accent',world.accent);$('title').textContent=plan.title;$('subject').textContent=plan.subject+' · APRENDE EXPLORANDO';$('intro').textContent=plan.introduction;$('world-name').textContent=world.title;
  if(config.courseId)$('back').href='/courses/'+encodeURIComponent(config.courseId)+'/';$('difficulty').value=config.adventure.difficulty;$('effects').checked=!media.matches;
  media.addEventListener('change',e=>{$('effects').checked=!e.matches;});
  selected=Math.max(0,plan.puzzles.findIndex(p=>!state.done[p.id]?.complete));$('app').hidden=false;$('loading').hidden=true;setMode('explore');update();$('stage').focus();requestAnimationFrame(frame);
}catch(error){$('loading').textContent=error.message;console.error(error);}})();
})();
