"""Composición de misiones accesibles y paquetes de aventura autocontenidos."""
from collections import deque
import hashlib
import json
from pathlib import Path
import random
import secrets

ENGINE=Path(__file__).resolve().parents[1]/'engine'


def layout(world, puzzles, seed):
    m=world['map'];w=m['width']*m['tilewidth'];h=m['height']*m['tileheight']
    layers={l['name']:l for l in m['layers']}
    collisions=layers['Colisiones']['objects']
    def walkable(x,y):
        return 40<=x<=w-40 and 72<=y<=h-28 and not any(x+7>o['x'] and x-7<o['x']+o['width'] and y+3>o['y'] and y-7<o['y']+o['height'] for o in collisions)
    spawn=layers['Inicio']['objects'][0];start=(round(spawn['x']/8)*8,round(spawn['y']/8)*8)
    if not walkable(*start): raise ValueError('El personaje no cabe en el punto de inicio')
    def has_approach_clearance(point):
        return all(walkable(point[0]+dx,point[1]+dy) for dx in (-16,-8,0,8,16) for dy in (-16,-8,0,8,16))
    clear_seen={start} if has_approach_clearance(start) else set()
    queue=deque(clear_seen)
    while queue:
        x,y=queue.popleft()
        for p in ((x+8,y),(x-8,y),(x,y+8),(x,y-8)):
            if p not in clear_seen and has_approach_clearance(p):clear_seen.add(p);queue.append(p)
    if not clear_seen: raise ValueError('El personaje no tiene una ruta despejada desde el inicio')
    stations=[];rng=random.Random(seed)
    spots=list(layers['Interacciones']['objects']);rng.shuffle(spots)
    if not spots: raise ValueError('El mapa necesita estaciones')
    for i,puzzle in enumerate(puzzles):
        spot=spots[i%len(spots)];sx=spot['x']+spot['width']/2;sy=spot['y']+spot['height']/2
        nearby=sorted(clear_seen,key=lambda p:(p[0]-sx)**2+(p[1]-sy)**2)
        point=next((p for p in nearby if all((p[0]-s['x'])**2+(p[1]-s['y'])**2>36**2 for s in stations)),None)
        if not point or (point[0]-sx)**2+(point[1]-sy)**2>110**2: raise ValueError('No hay espacio accesible para la misión')
        props={p['name']:p['value'] for p in spot.get('properties',[])}
        stations.append(dict(id=puzzle['id'],x=point[0],y=point[1],objectId=spot['id'],asset=props.get('asset_id'),title=puzzle['title']))
    exit_candidates=[p for p in clear_seen if all((p[0]-s['x'])**2+(p[1]-s['y'])**2>72**2 for s in stations)]
    if not exit_candidates: raise ValueError('No hay espacio accesible para el portal')
    exit_point=min(exit_candidates,key=lambda p:(p[0]-w/2)**2+(p[1]-100)**2)
    return dict(spawn=dict(x=start[0],y=start[1]),stations=stations,exit=dict(x=exit_point[0],y=exit_point[1]),
                bounds=dict(left=40,right=w-40,top=72,bottom=h-28))


def upgrade_package(package, difficulty='normal'):
    from .boss import build_boss
    if difficulty not in ('normal','calm','study'): raise ValueError('Ritmo inválido')
    config=package['config'];seed=secrets.randbelow(2**31-1)
    rng=random.Random(seed)
    ground=next(l for l in config['pixelWorld']['map']['layers'] if l['name']=='Suelo')
    ground['data']=[rng.randint(1,8) if 1<=gid<=8 else gid for gid in ground['data']]
    config['generationMode']='aventura';package['v']=3
    config['adventure']=dict(version=1,seed=seed,difficulty=difficulty,layout=layout(config['pixelWorld'],config['practice']['puzzles'],seed))
    config['boss']=build_boss([package],seed)
    config['adventureHash']=hashlib.sha256((config['planHash']+str(seed)).encode()).hexdigest()[:24]


def finalize_course(games, output):
    from .boss import build_boss
    packages=[];paths=[]
    for game in games:
        path=Path(output)/'games'/game['chunk_id']/'game.pkg.json'
        pkg=json.loads(path.read_text())
        if pkg.get('config',{}).get('generationMode')=='aventura':packages.append(pkg);paths.append(path)
    if not packages:return
    partial=any(g.get('status')!='success' for g in json.loads((Path(output)/'course-manifest.json').read_text())['games'])
    route=[dict(chunkId=p['config']['chunkId'],title=p['title'],hash=p['config']['adventureHash'],puzzleIds=[x['id'] for x in p['config']['practice']['puzzles']]) for p in packages]
    try:boss=build_boss(packages,packages[-1]['config']['adventure']['seed'],partial)
    except ValueError as error:boss=dict(status='failed',error=str(error))
    for i,(pkg,path) in enumerate(zip(packages,paths)):
        cfg=pkg['config'];cfg['courseRoute']=route;cfg['boss']=boss if i==len(packages)-1 else None
        path.write_text(json.dumps(pkg,ensure_ascii=False,indent=2),encoding='utf-8')
        path.with_name('index.html').write_text(render_html(pkg),encoding='utf-8')
    return boss['status']


def render_html(package):
    template=(ENGINE/'adventure/player.html').read_text()
    data=json.dumps(package,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=template.replace('<link rel="stylesheet" href="/engine/adventure/style.css">','<style>'+(ENGINE/'adventure/style.css').read_text()+'</style>')
    for script in ('bkt.js','adventure/core.js','adventure/encounters.js','adventure/runtime.js'):
        content='<script>'+(ENGINE/script).read_text()+'</script>'
        if script.endswith('runtime.js'):content=f'<script id="adventure-data" type="application/json">{data}</script>'+content
        template=template.replace(f'<script src="/engine/{script}"></script>',content)
    return template
