import {circuit,transformEquation,ecosystem} from './models.mjs';
const $=id=>document.getElementById(id);
const canvas=$('scene'),ctx=canvas.getContext('2d');
const imageCache=new Map();
const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
let manifest,world,map,objects=[],spots=[],assets={},paused=motionPreference.matches,requestId=0;
let electric={voltage:6,resistance:6,closed:true},equation={a:2,b:4,c:14},ecology={water:35,pollinators:50};
let focusedSpot=null,lastFrame=-1;
const format=n=>Number(n.toFixed(2)).toLocaleString('es');
function properties(item){return Object.fromEntries((item.properties||[]).map(p=>[p.name,p.value]));}
async function getJSON(path){const response=await fetch(path);if(!response.ok)throw new Error(`No se pudo abrir ${path} (${response.status})`);return response.json();}
function getImage(path){if(!imageCache.has(path)){imageCache.set(path,new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('No se pudo abrir la imagen '+path));im.src='../'+path;}));}return imageCache.get(path);}
let terrainImage,objectImages={},explorerImage;

async function selectWorld(id){
  const ticket=++requestId;
  const selected=manifest.worlds.find(w=>w.id===id)||manifest.worlds[0];
  $('loading').hidden=false;$('loading').textContent='Abriendo el atlas…';
  document.querySelectorAll('.world-button').forEach(button=>{const active=button.dataset.world===selected.id;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  try{
    const nextMap=await getJSON('../'+selected.map);
    const nextObjects=nextMap.layers.find(l=>l.name==='Escenario').objects;
    const required=[...new Set(nextObjects.map(o=>properties(o).asset_id))];
    const images=await Promise.all(required.map(async id=>[id,await getImage(assets[id].sheet||assets[id].image)]));
    const nextTerrain=await getImage(`art/exports/terrain-${selected.id}.png`);
    const explorer=await getImage(assets.explorer.sheet);
    if(ticket!==requestId)return;
    world=selected;map=nextMap;objects=nextObjects;spots=map.layers.find(l=>l.name==='Interacciones').objects;focusedSpot=null;
    objectImages=Object.fromEntries(images);terrainImage=nextTerrain;explorerImage=explorer;
    document.documentElement.style.setProperty('--accent',world.accent);
    $('world-title').textContent=world.title;$('world-location').textContent=world.location;$('subject').textContent=world.subject;
    $('subtitle').textContent=world.subtitle;$('objective').textContent=world.objective;$('map-link').href='../'+world.map;
    $('coordinate').textContent=String(manifest.worlds.indexOf(world)+1).padStart(2,'0');
    $('inspection').hidden=true;
    $('hotspots').replaceChildren(...spots.map((spot,index)=>{const button=document.createElement('button');button.type='button';button.className=properties(spot).action!=='info'?'primary':'';button.textContent=`${String(index+1).padStart(2,'0')}  ${spot.name}`;button.onclick=()=>inspect(spot);button.onfocus=()=>{focusedSpot=spot;draw(performance.now());};button.onblur=()=>{focusedSpot=null;draw(performance.now());};return button;}));
    renderActivity();$('loading').hidden=true;history.replaceState(null,'','#'+world.id);draw(performance.now());
  }catch(error){if(ticket===requestId)$('loading').textContent=error.message+'. Inicia la vista con serve.py y vuelve a cargar.';console.error(error);}
}

function draw(time){
  if(!map||!terrainImage)return;
  ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,768,512);
  const ground=map.layers.find(l=>l.type==='tilelayer');
  ground.data.forEach((gid,index)=>{const local=gid-1;ctx.drawImage(terrainImage,local%8*32,Math.floor(local/8)*32,32,32,index%24*32,Math.floor(index/24)*32,32,32);});
  const frameTime=paused?0:time;
  const items=objects.map(o=>({...o,asset:assets[properties(o).asset_id]}));
  // El personaje comparte la ordenación por profundidad de los objetos.
  items.push({x:334,y:390,width:32,height:48,asset:assets.explorer,character:true});
  items.sort((a,b)=>a.y-b.y);
  for(const item of items){
    const a=item.asset;let frame=paused?0:Math.floor(frameTime/a.frameDuration)%a.frames;
    if(item.character)frame=paused?0:Math.floor(frameTime/1800)%2;
    if(a.id==='lab-reactor'&&!electric.closed)frame=0;
    const image=item.character?explorerImage:objectImages[a.id];
    ctx.drawImage(image,frame*a.width,0,a.width,a.height,item.x,item.y-item.height,item.width,item.height);
  }
  // Iluminación ambiental de la vista; el arte exportado conserva píxeles opacos.
  if(world.id==='laboratory'){
    const current=circuit(electric.voltage,electric.resistance,electric.closed).current;
    const glow=ctx.createRadialGradient(384,208,8,384,208,120);glow.addColorStop(0,`rgba(104,243,211,${Math.min(.15,current*.04)})`);glow.addColorStop(1,'rgba(104,243,211,0)');ctx.fillStyle=glow;ctx.fillRect(264,88,240,240);
  }
  if(world.id==='biology'){
    for(let i=0;i<14;i++){const x=(i*97+Math.sin(frameTime/2500+i)*15+40)%768,y=(i*53+Math.cos(frameTime/2000+i)*9+35)%512;ctx.fillStyle=i%3?'#dcd693':'#a3d2b1';ctx.globalAlpha=.55;ctx.fillRect(Math.floor(x),Math.floor(y),2,2);}ctx.globalAlpha=1;
  }
  spots.forEach((spot,index)=>{
    const x=spot.x+22,y=spot.y-9,selected=focusedSpot===spot;
    ctx.fillStyle=selected?world.accent:'#13252eea';ctx.fillRect(x-11,y-11,22,22);ctx.strokeStyle=world.accent;ctx.lineWidth=1;ctx.strokeRect(x-11.5,y-11.5,23,23);
    ctx.fillStyle=selected?'#13252e':world.accent;ctx.font='11px monospace';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(index+1),x,y);
  });
}
function animate(time){if(!paused&&time-lastFrame>65){draw(time);lastFrame=time;}requestAnimationFrame(animate);}requestAnimationFrame(animate);
canvas.addEventListener('click',event=>{
  const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*768/rect.width,y=(event.clientY-rect.top)*512/rect.height;
  const spot=spots.find(s=>Math.abs(x-s.x-22)<38 && Math.abs(y-(s.y-9))<48);
  if(spot)inspect(spot);
});
function inspect(spot){
  const p=properties(spot);
  if(p.action==='info'){
    $('inspection-title').textContent=spot.name;$('inspection-text').textContent=p.text;$('inspection').hidden=false;
    $('inspection').scrollIntoView({behavior:paused?'instant':'smooth',block:'nearest'});
  }else{$('activity').scrollIntoView({behavior:paused?'instant':'smooth',block:'center'});$('activity').querySelector('input,button')?.focus({preventScroll:true});}
}
$('close-inspection').onclick=()=>{$('inspection').hidden=true;};
function updateMotion(){ $('motion').textContent=paused?'Activar animaciones':'Pausar animaciones';$('motion').setAttribute('aria-pressed',String(paused));draw(0);}
$('motion').onclick=()=>{paused=!paused;updateMotion();};updateMotion();
motionPreference.addEventListener('change',event=>{paused=event.matches;updateMotion();});

function completed(ok,text){$('completion').textContent=ok?'✦ '+text:'';}
function renderActivity(){
  $('completion').textContent='';
  if(world.id==='laboratory'){
    $('activity-title').innerHTML='Dale luz<br>a la estación.';
    $('activity').innerHTML=`<div class="activity-top"><h3>Consigue una corriente de 2 A</h3><small>CIRCUITO IDEAL · CC</small></div><div class="controls"><div><label class="slider-label" for="voltage">Voltaje de la batería <output id="voltage-value"></output></label><input id="voltage" type="range" min="0" max="24" value="${electric.voltage}"></div><div><label class="slider-label" for="resistance">Resistencia total <output id="resistance-value"></output></label><input id="resistance" type="range" min="2" max="12" value="${electric.resistance}"></div></div><div class="metrics"><div class="metric"><strong id="current"></strong><span>CORRIENTE</span></div><div class="metric"><strong id="power"></strong><span>POTENCIA</span></div><button class="primary-button" id="switch" type="button"></button></div><p id="activity-status" role="status" aria-live="polite"></p><p class="model-note">Modelo: fuente ideal y resistencia total constante. I = V / R; P = V × I. La lámpara del escenario es un indicador visual.</p>`;
    const update=()=>{const state=circuit(electric.voltage,electric.resistance,electric.closed);$('voltage-value').textContent=electric.voltage+' V';$('resistance-value').textContent=electric.resistance+' Ω';$('current').textContent=format(state.current)+' A';$('power').textContent=format(state.power)+' W';$('switch').textContent=electric.closed?'Abrir interruptor':'Cerrar interruptor';$('switch').setAttribute('aria-pressed',String(electric.closed));$('activity-status').textContent=state.complete?'¡Objetivo alcanzado! Hay varias combinaciones posibles.':electric.closed?'Observa qué cambia al modificar una sola variable.':'El circuito está abierto: la corriente es cero.';completed(state.complete,'Descubriste una relación entre voltaje y resistencia.');draw(performance.now());};
    $('voltage').oninput=e=>{electric.voltage=Number(e.target.value);update();};$('resistance').oninput=e=>{electric.resistance=Number(e.target.value);update();};$('switch').onclick=()=>{electric.closed=!electric.closed;update();};update();
  }else if(world.id==='mathematics'){
    $('activity-title').innerHTML='Encuentra<br>el equilibrio.';
    $('activity').innerHTML=`<div class="activity-top"><h3>Deja a x sola en un lado</h3><small>IGUALDAD · ECUACIONES</small></div><div class="equation" aria-live="polite"><span id="equation-left"></span><span class="equal">=</span><span id="equation-right"></span></div><div class="math-controls"><select id="operation" aria-label="Operación en ambos miembros"><option value="subtract">Restar a ambos lados</option><option value="divide">Dividir ambos lados entre</option><option value="add">Sumar a ambos lados</option><option value="multiply">Multiplicar ambos lados por</option></select><input id="amount" type="number" min="0.1" max="20" step="any" value="4" aria-label="Cantidad de la operación"><button id="apply" class="primary-button" type="button">Aplicar</button><button id="reset-math" class="secondary-button" type="button">Reiniciar</button></div><p id="math-log" class="math-log" role="status" aria-live="polite">Prueba a restar 4 en ambos miembros.</p><p class="model-note">La balanza representa una igualdad. Aplicamos la misma operación en ambos miembros; nunca dividimos entre cero.</p>`;
    const update=()=>{$('equation-left').textContent=(Math.abs(equation.a-1)<1e-8?'':format(equation.a))+'x'+(Math.abs(equation.b)<1e-8?'':(equation.b<0?' − ':' + ')+format(Math.abs(equation.b)));$('equation-right').textContent=format(equation.c);completed(equation.complete,'Resolviste la ecuación: x = 5.');};
    $('apply').onclick=()=>{try{equation=transformEquation(equation,$('operation').value,Number($('amount').value));$('math-log').textContent=equation.complete?'x = 5. Comprueba: 2 × 5 + 4 = 14.':'La igualdad se conserva. Continúa hasta aislar x.';update();}catch(error){$('math-log').textContent=error.message;}};
    $('reset-math').onclick=()=>{equation={a:2,b:4,c:14};$('math-log').textContent='Prueba a restar 4 en ambos miembros.';update();};update();
  }else{
    $('activity-title').innerHTML='Cuida cada<br>conexión.';
    $('activity').innerHTML=`<div class="activity-top"><h3>Favorece la reproducción de las plantas</h3><small>FACTORES LIMITANTES</small></div><div class="controls"><div><label class="slider-label" for="water">Disponibilidad de agua <output id="water-value"></output></label><input id="water" type="range" min="0" max="100" value="${ecology.water}"></div><div><label class="slider-label" for="pollinators">Actividad de polinizadores <output id="pollinators-value"></output></label><input id="pollinators" type="range" min="0" max="100" value="${ecology.pollinators}"></div></div><div class="metrics"><div class="metric"><strong id="reproduction"></strong><span>ÍNDICE ILUSTRATIVO / 100</span></div><div><small>FACTOR LIMITANTE</small><p id="limiting"></p></div></div><div class="meter" aria-hidden="true"><span id="eco-meter"></span></div><p id="activity-status" role="status" aria-live="polite"></p><p class="model-note">Modelo didáctico: índice = mínimo(agua, polinización). Supone que los demás factores son suficientes; no representa una especie concreta ni predice un ecosistema real.</p>`;
    const update=()=>{const state=ecosystem(ecology.water,ecology.pollinators);$('water-value').textContent=ecology.water+'/100';$('pollinators-value').textContent=ecology.pollinators+'/100';$('reproduction').textContent=state.reproduction;$('limiting').textContent=state.limiting;$('eco-meter').style.width=state.reproduction+'%';$('activity-status').textContent=state.complete?'Las dos condiciones superan 75. Ahora baja una y observa.':'Lleva el índice hasta 75. ¿Basta con aumentar un solo factor?';completed(state.complete,'Identificaste cómo un factor puede limitar al conjunto.');};
    $('water').oninput=e=>{ecology.water=Number(e.target.value);update();};$('pollinators').oninput=e=>{ecology.pollinators=Number(e.target.value);update();};update();
  }
}

try{
  manifest=await getJSON('../manifest.json');assets=Object.fromEntries(manifest.assets.map(a=>[a.id,a]));
  $('worlds').replaceChildren(...manifest.worlds.map((w,index)=>{
    const button=document.createElement('button');button.type='button';button.className='world-button';button.dataset.world=w.id;button.setAttribute('aria-pressed','false');
    const thumb=document.createElement('div');thumb.className='world-thumb';const image=document.createElement('img');image.src='../'+w.preview;image.alt='';thumb.append(image);
    const number=document.createElement('span');number.className='world-number';number.textContent='0'+(index+1);thumb.append(number);
    const copy=document.createElement('div');copy.className='world-button-copy';const small=document.createElement('small');small.textContent=w.subject;const title=document.createElement('strong');title.textContent=w.title;const arrow=document.createElement('span');arrow.className='world-arrow';arrow.textContent='↗';copy.append(small,title,arrow);button.append(thumb,copy);button.onclick=()=>selectWorld(w.id);return button;
  }));
  await selectWorld(location.hash.slice(1));
}catch(error){$('loading').textContent=error.message;console.error(error);}
