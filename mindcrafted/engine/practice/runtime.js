/* Motor de puzzles de datos: nunca evalúa código generado por la IA. */
(function(){
'use strict';
const $=id=>document.getElementById(id),canvas=$('world'),ctx=canvas.getContext('2d');
const kinds={balance_equation:'Balanza de ecuaciones',fraction_fill:'Constructor de fracciones',circuit_target:'Circuito de precisión',concept_links:'Conecta las ideas',process_order:'Reconstruye el proceso',evidence_choice:'Resuelve con evidencias'};
const media=matchMedia('(prefers-reduced-motion: reduce)');let paused=media.matches,config,plan,world,images={},index=0,progress={},storageKey,tracker,currentCheck,puzzleLocked=false,lastFrame=0;
const format=n=>Number(n.toFixed(3)).toLocaleString('es');
function el(tag,content,cls){const node=document.createElement(tag);if(content!==undefined)node.textContent=content;if(cls)node.className=cls;return node;}
function button(label,action,cls){const b=el('button',label,cls);b.type='button';b.onclick=action;return b;}
function shuffled(values){const list=values.slice();for(let i=list.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[list[i],list[j]]=[list[j],list[i]];}if(list.length>1&&list.every((v,i)=>v===values[i]))list.push(list.shift());return list;}
function save(){try{localStorage.setItem(storageKey,JSON.stringify(progress));}catch(_){$('mastery').textContent='El navegador no permite guardar el progreso.';}}
function feedback(message,wrong=false){$('feedback').textContent=message;$('feedback').classList.toggle('wrong',wrong);}
function dataOf(object){return Object.fromEntries((object.properties||[]).map(p=>[p.name,p.value]));}
function motion(){ $('motion').textContent=paused?'Activar animaciones':'Pausar animaciones';$('motion').setAttribute('aria-pressed',String(paused));draw(0);}
$('motion').onclick=()=>{paused=!paused;motion();};media.addEventListener('change',e=>{paused=e.matches;motion();});
function draw(time){
  if(!world||!images['terrain-'+world.id])return;
  ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,768,512);
  const ground=world.map.layers.find(l=>l.type==='tilelayer');
  ground.data.forEach((gid,i)=>ctx.drawImage(images['terrain-'+world.id],(gid-1)%8*32,Math.floor((gid-1)/8)*32,32,32,i%24*32,Math.floor(i/24)*32,32,32));
  const objects=world.map.layers.find(l=>l.name==='Escenario').objects.map(o=>({...o,asset:dataOf(o).asset_id}));
  objects.push({x:334,y:390,width:32,height:48,asset:'explorer'});objects.sort((a,b)=>a.y-b.y);
  objects.forEach(o=>{const a=world.assets[o.asset];let frame=paused?0:Math.floor(time/a.frameDuration)%a.frames;if(o.asset==='explorer')frame=paused?0:Math.floor(time/1500)%2;ctx.drawImage(images[o.asset],frame*a.width,0,a.width,a.height,o.x,o.y-o.height,o.width,o.height);});
  plan.puzzles.forEach((p,i)=>{const x=110+i*(548/Math.max(1,plan.puzzles.length-1)),y=world.id==='biology'?300:280;ctx.fillStyle=i===index?world.accent:'#13252e';ctx.fillRect(x-16,y-16,32,32);ctx.strokeStyle=world.accent;ctx.strokeRect(x-16,y-16,32,32);ctx.fillStyle=i===index?'#13252e':world.accent;ctx.font='14px monospace';ctx.textAlign='center';ctx.fillText(progress[p.id]?.done?'✓':i+1,x,y+5);});
}
function animate(t){if(!paused&&t-lastFrame>70){draw(t);lastFrame=t;}requestAnimationFrame(animate);}requestAnimationFrame(animate);
canvas.onclick=e=>{const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)*768/r.width,y=(e.clientY-r.top)*512/r.height;plan.puzzles.forEach((_,i)=>{const px=110+i*(548/Math.max(1,plan.puzzles.length-1));if(Math.abs(x-px)<25&&Math.abs(y-(world.id==='biology'?300:280))<25)show(i);});};
function updateProgress(){
  const completed=plan.puzzles.filter(p=>progress[p.id]?.done).length;
  $('progress-count').textContent=completed+' / '+plan.puzzles.length;$('progress').max=plan.puzzles.length;$('progress').value=completed;
  const summary=tracker?.summary();$('mastery').textContent=summary?'Dominio estimado: '+Math.round(summary.mastery*100)+'%':'';
  $('puzzles').replaceChildren(...plan.puzzles.map((p,i)=>{const b=button((i+1)+'. '+p.title,()=>show(i),(i===index?'active ':'')+(progress[p.id]?.done?'done':''));b.setAttribute('aria-current',i===index?'step':'false');return b;}));
  $('finished').hidden=completed!==plan.puzzles.length;
  $('finished-copy').textContent='Has completado '+completed+' retos y obtenido '+plan.puzzles.reduce((n,p)=>n+(progress[p.id]?.score||0),0)+' puntos. Puedes seguir practicando o pasar a la siguiente lección.';
  const next=config.nextGameUrl;
  $('next-lesson').href=next||$('back').href;$('next-lesson').textContent=next?'Siguiente lección →':'Volver al curso →';draw(performance.now());
}
function show(i){
  index=i;const p=plan.puzzles[i];puzzleLocked=!!progress[p.id]?.done;
  $('puzzle-kind').textContent=(i+1)+' / '+plan.puzzles.length+' · '+kinds[p.kind];$('puzzle-title').textContent=p.title;$('instruction').textContent=p.instruction;
  $('evidence').textContent=p.evidence;$('source').open=false;$('exercise').replaceChildren();feedback(puzzleLocked?'Ya completaste este reto. Puedes reiniciarlo para practicar otra vez.':'');
  $('check').disabled=puzzleLocked;$('hint').disabled=puzzleLocked;$('next').textContent=i===plan.puzzles.length-1?'Volver al primer reto ↺':'Siguiente reto →';
  builders[p.kind]($('exercise'),p.data);updateProgress();
}
function record(correct){
  const p=plan.puzzles[index],r=progress[p.id]||{attempts:0,hints:0};r.attempts++;const score=correct?Math.max(40,100-(r.attempts-1)*10-r.hints*5):0;
  tracker?.observe(p.skillId,correct,{label:p.concept,score});
  if(correct){r.done=true;r.score=Math.max(r.score||0,score);puzzleLocked=true;$('check').disabled=true;$('hint').disabled=true;feedback('✓ '+p.explanation);}
  else feedback('Aún no coincide. '+p.hint,true);
  progress[p.id]=r;save();updateProgress();
}
$('check').onclick=()=>{if(!puzzleLocked)record(currentCheck());};
$('hint').onclick=()=>{const p=plan.puzzles[index],r=progress[p.id]||{attempts:0,hints:0};r.hints++;progress[p.id]=r;save();feedback(p.hint);};
$('restart').onclick=()=>{puzzleLocked=false;show(index);puzzleLocked=false;$('check').disabled=false;$('hint').disabled=false;feedback('Nuevo intento. Tu mejor resultado se conserva.');};
$('next').onclick=()=>show((index+1)%plan.puzzles.length);

const builders={
  balance_equation(host,d){
    let a=d.a,b=d.b,c=d.c;const display=el('div','','equation'),beam=el('div','','balanced-beam');display.setAttribute('aria-live','polite');
    const controls=el('div',undefined,'equation-controls'),select=el('select');select.setAttribute('aria-label','Operación en ambos miembros');
    for(const [value,label] of [['subtract','Restar a ambos lados'],['divide','Dividir ambos lados entre'],['add','Sumar a ambos lados'],['multiply','Multiplicar ambos lados por']]){const option=el('option',label);option.value=value;select.append(option);}
    const amount=el('input');amount.type='number';amount.min='0.1';amount.max='20';amount.step='any';amount.value=String(Math.abs(b)||a);amount.setAttribute('aria-label','Cantidad');
    const update=()=>{display.textContent=(Math.abs(a-1)<1e-7?'':format(a))+'x'+(Math.abs(b)<1e-7?'':(b<0?' − ':' + ')+format(Math.abs(b)))+' = '+format(c);};
    controls.append(select,amount,button('Aplicar',()=>{const n=Number(amount.value);if(!Number.isFinite(n)||n<=0||n>20){feedback('Usa una cantidad mayor que cero y como máximo 20.',true);return;}let next;
      if(select.value==='subtract')next=[a,b-n,c-n];else if(select.value==='add')next=[a,b+n,c+n];else if(select.value==='divide')next=[a/n,b/n,c/n];else next=[a*n,b*n,c*n];
      if(next.some(v=>!Number.isFinite(v)||Math.abs(v)>10000)||Math.abs(next[0])<1e-8){feedback('Reinicia el reto para trabajar con cantidades pequeñas.',true);return;}[a,b,c]=next;update();feedback('Aplicaste la misma operación a ambos miembros.');}));
    host.append(display,beam,controls,el('p','Conserva la igualdad hasta dejar x sola en el lado izquierdo.','equation-note'));update();
    currentCheck=()=>Math.abs(a-1)<1e-7&&Math.abs(b)<1e-7&&Math.abs(c-d.solution)<1e-6;
  },
  fraction_fill(host,d){
    const selected=new Set(),pieces=el('div',undefined,'fraction-pieces');host.append(el('div',d.numerator+' / '+d.denominator,'fraction-target'));
    for(let i=0;i<d.denominator;i++){const b=button('Parte '+(i+1),()=>{selected.has(i)?selected.delete(i):selected.add(i);b.classList.toggle('selected',selected.has(i));b.setAttribute('aria-pressed',String(selected.has(i)));});b.setAttribute('aria-pressed','false');pieces.append(b);}
    host.append(pieces,el('p','Selecciona partes del mismo tamaño para representar la fracción.','model-note'));currentCheck=()=>selected.size===d.numerator;
  },
  circuit_target(host,d){
    let closed=true;const diagram=el('div',undefined,'circuit-diagram');diagram.append(el('span','Batería'),el('span','→'),el('span',d.resistance+' Ω'),el('span','→'),el('span','Lámpara'));
    const label=el('label',undefined,'slider-row'),out=el('output'),slider=el('input');slider.type='range';slider.min='0';slider.max='24';slider.value='0';slider.id='practice-voltage';label.htmlFor=slider.id;label.append(el('span','Voltaje'),out);
    const current=el('div',undefined,'meter-value'),toggle=button('Abrir interruptor',()=>{closed=!closed;toggle.textContent=closed?'Abrir interruptor':'Cerrar interruptor';toggle.setAttribute('aria-pressed',String(closed));update();});toggle.setAttribute('aria-pressed','true');
    const update=()=>{out.textContent=slider.value+' V';current.textContent=format(closed?Number(slider.value)/d.resistance:0)+' A';};slider.oninput=update;
    host.append(el('p','Objetivo: '+format(d.target_current)+' A'),diagram,label,slider,current,toggle,el('p','Modelo ideal de corriente continua: I = V / R. La resistencia indicada representa la resistencia total del circuito.','model-note'));update();currentCheck=()=>closed&&Number(slider.value)===d.target_voltage;
  },
  concept_links(host,d){
    let left=null;const links=new Map(),columns=el('div',undefined,'link-columns'),lcol=el('div',undefined,'link-column'),rcol=el('div',undefined,'link-column');const leftButtons=[],rightButtons=[],rightOrder=shuffled(d.pairs.map((_,i)=>i));const labels=new Map(rightOrder.map((id,pos)=>[id,String.fromCharCode(65+pos)]));
    function update(){leftButtons.forEach((b,i)=>{b.classList.toggle('selected',left===i);b.classList.toggle('linked',links.has(i));b.setAttribute('aria-pressed',String(left===i));b.textContent=(links.has(i)?'['+labels.get(links.get(i))+'] ':'')+d.pairs[i].left;});rightButtons.forEach(({b,i})=>b.classList.toggle('linked',[...links.values()].includes(i)));}
    d.pairs.forEach((pair,i)=>{const b=button(pair.left,()=>{left=i;update();});leftButtons.push(b);lcol.append(b);});
    rightOrder.forEach(i=>{const b=button(labels.get(i)+'. '+d.pairs[i].right,()=>{if(left===null){feedback('Selecciona primero una idea de la columna izquierda.');return;}for(const [k,v] of links)if(v===i)links.delete(k);links.set(left,i);left=null;update();});rightButtons.push({b,i});rcol.append(b);});
    columns.append(lcol,rcol);host.append(columns,el('p','Elige una idea y después su relación. Puedes cambiar cualquier conexión.','connection-note'));update();currentCheck=()=>links.size===d.pairs.length&&d.pairs.every((_,i)=>links.get(i)===i);
  },
  process_order(host,d){
    const order=shuffled(d.steps.map((_,i)=>i)),list=el('div',undefined,'sequence');
    function render(){list.replaceChildren(...order.map((id,i)=>{const row=el('div',undefined,'sequence-row'),up=button('↑',()=>{[order[i-1],order[i]]=[order[i],order[i-1]];render();}),down=button('↓',()=>{[order[i],order[i+1]]=[order[i+1],order[i]];render();});up.disabled=i===0;down.disabled=i===order.length-1;up.setAttribute('aria-label','Subir: '+d.steps[id]);down.setAttribute('aria-label','Bajar: '+d.steps[id]);row.append(el('span',(i+1)+'. '+d.steps[id]),up,down);return row;}));}
    host.append(list);render();currentCheck=()=>order.every((id,i)=>id===i);
  },
  evidence_choice(host,d){
    let choice=null;const choices=el('div',undefined,'choices');choices.setAttribute('role','group');choices.setAttribute('aria-label','Opciones');
    shuffled(d.options.map((_,i)=>i)).forEach(i=>{const b=button(d.options[i],()=>{choice=i;for(const c of choices.children){c.classList.remove('selected');c.setAttribute('aria-pressed','false');}b.classList.add('selected');b.setAttribute('aria-pressed','true');});b.setAttribute('aria-pressed','false');choices.append(b);});host.append(choices);currentCheck=()=>choice===d.answer;
  }
};

(async function init(){try{
  const inline=$('practice-data'),params=new URLSearchParams(location.search);let pkg;
  if(inline)pkg=JSON.parse(inline.textContent);else{const course=params.get('course'),game=params.get('game');if(!course||!game)throw new Error('Abre esta práctica desde un curso.');const response=await fetch('/api/play/'+encodeURIComponent(course)+'/'+encodeURIComponent(game)+'/package');if(!response.ok)throw new Error('No se pudo cargar la práctica.');pkg=await response.json();}
  config=pkg.config;plan=config.practice;world=config.pixelWorld;if(!plan?.puzzles?.length||!world)throw new Error('El paquete no contiene puzzles válidos.');
  document.title=plan.title+' · MindCrafted';document.documentElement.style.setProperty('--accent',world.accent);
  $('subject').textContent=plan.subject+' · PRÁCTICA PERSONALIZADA';$('title').textContent=plan.title;$('introduction').textContent=plan.introduction;$('world-name').textContent=world.title;
  const course=config.courseId||config.sourceHash;storageKey='mindcrafted_practice_v1:'+course+':'+config.chunkId+':'+config.planHash;
  try{const raw=JSON.parse(localStorage.getItem(storageKey)||'{}');if(raw&&typeof raw==='object'&&!Array.isArray(raw))for(const p of plan.puzzles){const r=raw[p.id];if(r&&typeof r==='object')progress[p.id]={done:r.done===true,attempts:Math.max(0,Number(r.attempts)||0),hints:Math.max(0,Number(r.hints)||0),score:Math.min(100,Math.max(0,Number(r.score)||0))};}}catch(_){}
  tracker=window.MindCraftedBKT?.createTracker({scope:course});
  if(config.courseId)$('back').href='/courses/'+encodeURIComponent(config.courseId)+'/';
  images=Object.fromEntries(await Promise.all(Object.entries(world.assets).map(([id,a])=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve([id,image]);image.onerror=()=>reject(new Error('No se pudo abrir el recurso '+id));image.src=a.image;}))));
  $('practice-app').hidden=false;$('load-status').hidden=true;const first=plan.puzzles.findIndex(p=>!progress[p.id]?.done);show(first<0?0:first);motion();
}catch(error){$('load-status').textContent=error.message;console.error(error);}})();
})();
