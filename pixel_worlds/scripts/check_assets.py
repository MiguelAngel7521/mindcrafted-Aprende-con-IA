#!/usr/bin/env python3
"""Comprueba referencias, formatos PNG/Aseprite y accesibilidad de interacciones."""
import json
from pathlib import Path
import struct
from collections import deque

ROOT=Path(__file__).resolve().parents[1]


def png_size(path):
    raw=path.read_bytes()
    assert raw[:8]==b'\x89PNG\r\n\x1a\n',f"PNG inválido: {path}"
    return struct.unpack('>II',raw[16:24])


def check():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for asset in manifest['assets']:
        assert png_size(ROOT/asset['image'])==(asset['width'],asset['height']),asset['id']
        raw=(ROOT/asset['source']).read_bytes()
        assert raw[4:6]==b'\xe0\xa5',asset['source']
        assert struct.unpack('<HHH',raw[6:12])==(asset['frames'],asset['width'],asset['height']),asset['source']
        if asset.get('sheet'):
            assert png_size(ROOT/asset['sheet'])==(asset['width']*asset['frames'],asset['height']),asset['sheet']
    for world in manifest['worlds']:
        path=ROOT/world['map'];data=json.loads(path.read_text());ids=set()
        assert png_size(ROOT/world['preview'])==(768,512),world['preview']
        for ts in data['tilesets']:
            ts_path=path.parent/ts['source'];tileset=json.loads(ts_path.read_text())
            if 'image' in tileset:assert (ts_path.parent/tileset['image']).is_file()
            for tile in tileset.get('tiles',[]):
                if 'image' in tile:assert (ts_path.parent/tile['image']).is_file()
        for layer in data['layers']:
            if layer['type']=='tilelayer':assert len(layer['data'])==data['width']*data['height']
            for obj in layer.get('objects',[]):
                assert obj['id'] not in ids;ids.add(obj['id'])
                # Árboles de borde se recortan deliberadamente por el encuadre.
                assert obj['x']<768 and obj['x']+obj.get('width',1)>0 and 0<=obj['y']<=512,(world['id'],obj)
        assert data['nextobjectid']>max(ids)
        # La capa de inicio no puede quedar dentro de un obstáculo.
        spawn=next(l for l in data['layers'] if l['name']=='Inicio')['objects'][0]
        collisions=next(l for l in data['layers'] if l['name']=='Colisiones')['objects']
        def blocked(x,y):return any(o['x']<=x<o['x']+o['width'] and o['y']<=y<o['y']+o['height'] for o in collisions)
        assert not blocked(spawn['x'],spawn['y']),f"Inicio bloqueado: {world['id']}"
        # Conectividad a una zona junto a cada objeto interactivo, sobre rejilla fina.
        start=(round(spawn['x']/8),round(spawn['y']/8));seen={start};queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nxt=(x+dx,y+dy)
                if 4<=nxt[0]<92 and 8<=nxt[1]<60 and nxt not in seen and not blocked(nxt[0]*8,nxt[1]*8):seen.add(nxt);queue.append(nxt)
        interactions=next(l for l in data['layers'] if l['name']=='Interacciones')['objects']
        for spot in interactions:
            assert any(abs(x*8-(spot['x']+22))<75 and abs(y*8-(spot['y']+22))<75 for x,y in seen),f"Interacción inaccesible: {world['id']}/{spot['name']}"
    print(f"OK: {len(manifest['assets'])} originales, imágenes, animaciones y {len(manifest['worlds'])} mapas con referencias válidas e interacciones accesibles.")


if __name__=='__main__':check()
