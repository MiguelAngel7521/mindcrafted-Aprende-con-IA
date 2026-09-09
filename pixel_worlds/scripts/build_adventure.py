"""Añade arte de aventura en archivos nuevos; nunca redibuja originales existentes."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    manifest = json.loads((ROOT/'manifest.json').read_text())
    if any(w['id'] == 'technology' for w in manifest['worlds']):
        raise SystemExit('Nexo ya existe. Edita sus originales y usa export_assets.lua; no se sobrescribe.')
    binary = shutil.which('aseprite') or str(Path.home()/'aseprite/build/bin/aseprite')
    with tempfile.TemporaryDirectory(prefix='mindcrafted-art-') as tmp:
        staging = Path(tmp)
        for folder in ('source', 'exports'): (staging/folder).mkdir()
        subprocess.run([binary, '--batch', '--script-param', f'output={staging}', '--script', str(ROOT/'scripts/draw_adventure.lua')], check=True)
        assets = json.loads((staging/'catalog.json').read_text())
        for folder in ('source', 'exports'):
            for file in (staging/folder).iterdir():
                target = ROOT/'art'/folder/file.name
                if target.exists(): raise ValueError(f'Ya existe {target}')
        for folder in ('source', 'exports'):
            for file in (staging/folder).iterdir(): shutil.copyfile(file, ROOT/'art'/folder/file.name)
    manifest['assets'].extend(assets)
    world = dict(id='technology', title='Nexo Digital', subject='Tecnología', accent='#65e5d1',
                 subtitle='Reconecta el conocimiento.', location='Nexo · Centro de datos',
                 objective='Aplicar conceptos tecnológicos para restaurar estaciones y conexiones.',
                 mechanic='packet_route', map='maps/technology.tmj', preview='previews/technology.png')
    manifest['worlds'].append(world)
    tiles = [a for a in assets if a['id'].startswith('tech-')]
    write(ROOT/'tilesets/technology-objects.tsj', dict(type='tileset', version='1.10', name='Objetos Nexo', columns=0,
        tilewidth=64, tileheight=96, tilecount=len(tiles), objectalignment='bottomleft',
        tiles=[dict(id=i, image='../'+a['image'], imagewidth=a['width'], imageheight=a['height']) for i,a in enumerate(tiles)]))
    write(ROOT/'tilesets/technology.tsj', dict(type='tileset', version='1.10', name='Nexo', columns=8, tilecount=16,
        tilewidth=32, tileheight=32, image='../art/exports/terrain-technology.png', imagewidth=256, imageheight=64))
    objects=[]; collisions=[]; interactions=[]; uid=1
    for name,x,y in [('tech-server',80,205),('tech-server',620,205),('tech-server',80,400),('tech-server',620,400),
                     ('tech-terminal',260,218),('tech-terminal',460,218),('tech-terminal',260,395),('tech-terminal',460,395),('tech-beacon',370,145)]:
        i=next(i for i,a in enumerate(tiles) if a['id']==name);a=tiles[i]
        objects.append(dict(id=uid,name=name,gid=100+i,x=x,y=y,width=a['width'],height=a['height'],visible=True,
                            properties=[dict(name='asset_id',type='string',value=name)]));uid+=1
        collisions.append(dict(id=uid,name=name,x=x+4,y=y-16,width=a['width']-8,height=16));uid+=1
        if name!='tech-server':
            interactions.append(dict(id=uid,name='Estación de conexión',x=x,y=y-40,width=a['width'],height=40,
                properties=[dict(name='action',type='string',value='mission'),dict(name='asset_id',type='string',value=name)]));uid+=1
    ground=[9+(x+y)%4 if y<2 or y==15 or x in (0,23) else 13 if x in (11,12) else 1+(x*3+y*5)%8 for y in range(16) for x in range(24)]
    layers=[dict(id=1,name='Suelo',type='tilelayer',width=24,height=16,data=ground,visible=True,opacity=1,x=0,y=0)]
    for i,(name,items) in enumerate([('Escenario',objects),('Interacciones',interactions),('Colisiones',collisions),('Inicio',[dict(id=uid,name='Inicio',point=True,x=384,y=440)])],2):
        layers.append(dict(id=i,name=name,type='objectgroup',objects=items,visible=name=='Escenario',opacity=1,x=0,y=0,draworder='topdown'))
    write(ROOT/'maps/technology.tmj', dict(type='map',version='1.10',tiledversion='1.12.2',orientation='orthogonal',renderorder='right-down',
        width=24,height=16,tilewidth=32,tileheight=32,infinite=False,nextobjectid=uid+1,nextlayerid=6,layers=layers,
        tilesets=[dict(firstgid=1,source='../tilesets/technology.tsj'),dict(firstgid=100,source='../tilesets/technology-objects.tsj')]))
    write(ROOT/'manifest.json',manifest);write(ROOT/'art/catalog.json',manifest['assets'])
    print('Añadidos Nexo Digital, personaje direccional y tres familias de jefes.')


if __name__=='__main__': main()
