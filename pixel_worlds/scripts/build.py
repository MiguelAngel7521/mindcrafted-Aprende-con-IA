#!/usr/bin/env python3
"""Construye recursos con Aseprite y mapas nativos Tiled. Sin dependencias Python.

La regeneración se hace en una carpeta temporal y se publica tras validar la
salida de Aseprite. No pisa fuentes manualmente editadas: exige --replace-art.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCENES = [
    dict(id="laboratory", title="El laboratorio de la luz", subject="Física",
         subtitle="Conecta ideas. Enciende posibilidades.", accent="#78ddd0",
         objective="Relacionar voltaje, resistencia y corriente en un circuito de corriente continua ideal.",
         mechanic="circuit", location="Estación Aurora · Taller 01"),
    dict(id="mathematics", title="El taller del equilibrio", subject="Matemáticas",
         subtitle="Cada cambio tiene dos lados.", accent="#ebc184",
         objective="Resolver una ecuación lineal conservando la igualdad en ambos miembros.",
         mechanic="balance", location="Biblioteca Áurea · Sala 02"),
    dict(id="biology", title="El bosque de los vínculos", subject="Biología",
         subtitle="Un mundo pequeño. Muchas conexiones.", accent="#b3d78a",
         objective="Explorar cómo agua y polinización limitan la reproducción de plantas en un modelo didáctico.",
         mechanic="ecosystem", location="Reserva Niebla · Sendero 03"),
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def props(**values: object) -> list[dict]:
    return [{"name": key, "type": "bool" if isinstance(value, bool) else "int" if isinstance(value, int) else "string", "value": value}
            for key, value in values.items()]


def generate_maps(catalog: list[dict], target: Path) -> dict:
    w, h, tile = 24, 16, 32
    assets = {a["id"]: a for a in catalog}
    objects = [a for a in catalog if not a["id"].startswith("terrain-")]
    gids = {a["id"]: 100 + i for i, a in enumerate(objects)}
    write_json(target / "tilesets/objects.tsj", {
        "type": "tileset", "version": "1.10", "tiledversion": "1.12.2", "name": "Objetos MindCrafted",
        "columns": 0, "grid": {"orientation": "orthogonal", "width": 1, "height": 1},
        "objectalignment": "bottomleft", "tilewidth": max(a["width"] for a in objects),
        "tileheight": max(a["height"] for a in objects), "tilecount": len(objects),
        "tiles": [{"id": i, "image": "../" + a["image"], "imagewidth": a["width"], "imageheight": a["height"],
                   "properties": props(asset_id=a["id"], frames=a["frames"], source="../" + a["source"])} for i, a in enumerate(objects)],
    })
    manifest = {"version": 1, "tileSize": tile, "width": w * tile, "height": h * tile,
                "assets": catalog, "worlds": [], "license": "AGPL-3.0-or-later"}
    for scene in SCENES:
        sid = scene["id"]
        rand = random.Random(sid)
        write_json(target / f"tilesets/{sid}.tsj", {
            "type": "tileset", "version": "1.10", "tiledversion": "1.12.2", "name": scene["subject"],
            "image": f"../art/exports/terrain-{sid}.png", "imagewidth": 256, "imageheight": 64,
            "tilewidth": tile, "tileheight": tile, "tilecount": 16, "columns": 8, "margin": 0, "spacing": 0,
            "tiles": [{"id": i, "properties": props(kind=("water" if sid == "biology" and 8 <= i < 12 else "wall" if sid != "biology" and 8 <= i < 12 else "ground"))} for i in range(16)]
        })
        ground = [rand.randrange(1, 9) for _ in range(w*h)]
        decorations, interactions, collisions = [], [], []
        next_id = 1

        def add(asset: str, x: int, bottom: int, label: str = "", action: str = "", body: str = "", solid: bool = True):
            nonlocal next_id
            a = assets[asset]
            left = x - a["width"] // 2
            decorations.append({"id": next_id, "name": asset, "gid": gids[asset], "x": left, "y": bottom,
                                "width": a["width"], "height": a["height"], "rotation": 0, "visible": True,
                                "properties": props(asset_id=asset)})
            next_id += 1
            if solid:
                footprint = max(12, min(28, a["height"] // 4))
                collisions.append({"id": next_id, "name": asset, "x": left+8, "y": bottom-footprint-4,
                                   "width": a["width"]-16, "height": footprint, "rotation": 0, "visible": True})
                next_id += 1
            if label:
                interactions.append({"id": next_id, "name": label, "x": x-22, "y": bottom-a["height"]//2-22,
                                     "width": 44, "height": 44, "rotation": 0, "visible": True,
                                     "properties": props(action=action, text=body, asset_id=asset)})
                next_id += 1

        if sid != "biology":
            for y in range(h):
                for x in range(w):
                    if y < 2 or y == h-1 or x in (0,w-1): ground[y*w+x] = 9+(x+y)%4
            for y in range(3,14):
                ground[y*w+10] = 16
                ground[y*w+13] = 16
            add("shared-door",384,109,solid=False)
            add("shared-planter",72,126); add("shared-planter",696,126)
        if sid == "laboratory":
            for x in range(9,15): ground[7*w+x] = 14
            add("lab-reactor",384,252,"Núcleo de energía","circuit","Ajusta un circuito ideal y observa cómo cambia la corriente.")
            add("lab-console",384,435,"Osciloscopio","info","Los instrumentos permiten observar y medir. En esta demostración, la corriente se calcula con I = V / R.")
            add("lab-workbench",145,235,"Mesa de componentes","info","Una batería mantiene una diferencia de potencial. Una resistencia limita la corriente del circuito.")
            add("lab-workbench",623,235)
            add("lab-coil",130,414);add("lab-coil",642,414)
            add("lab-battery",238,349);add("lab-battery",523,349)
            add("lab-lamp",82,334);add("lab-lamp",686,334)
            add("shared-planter",70,461);add("shared-planter",698,461)
        elif sid == "mathematics":
            add("math-board",384,165,"Cuaderno de ideas","info","La igualdad se conserva al realizar la misma operación en ambos miembros. La balanza representa esa relación.")
            add("math-library",132,194);add("math-library",638,194)
            add("math-balance",384,322,"Balanza de ecuaciones","balance","Descubre el valor de x conservando el equilibrio.")
            add("math-table",153,351,"Mesa de geometría","info","Las representaciones visuales ayudan a relacionar cantidades, áreas y proporciones.")
            add("math-orrery",620,358,"Modelo orbital","info","Los modelos matemáticos representan relaciones. Sus simplificaciones deben explicarse.")
            add("math-table",270,459);add("math-table",514,459)
            add("math-crate",84,452);add("math-crate",680,452)
        else:
            import math
            for y in range(h):
                center=18+int(math.sin(y/2.8)*1.2)
                for x in range(w):
                    if center-1 <= x <= center+1: ground[y*w+x]=9+rand.randrange(4)
                    elif x in (center-2,center+2): ground[y*w+x]=13+rand.randrange(4)
                    elif 9 <= x <= 11 or 8 <= y <= 9: ground[y*w+x]=13+rand.randrange(4)
            for x,y in [(58,131),(152,156),(264,125),(419,135),(508,118),(705,128),(66,314),(711,315),(68,488),(177,487),(480,495),(719,493)]:
                add("forest-oak",x,y)
            for x,y in [(33,207),(217,138),(459,194),(739,225),(96,404),(692,422)]: add("forest-pine",x,y)
            add("forest-beehive",416,260,"El jardín de los vínculos","ecosystem","Explora cómo se relacionan agua, plantas y polinizadores.")
            add("forest-sign",289,382,"Diario de campo","info","Observa las relaciones entre organismos y recursos. Este escenario utiliza un modelo didáctico simplificado.")
            add("forest-rock",497,378,"Agua y hábitat","info","El agua disponible influye en el crecimiento de las plantas. Cada especie tiene necesidades propias.")
            for x,y in [(166,292),(235,215),(402,386),(628,436),(148,422),(668,227)]: add("forest-fern",x,y,solid=False)
            for x,y in [(117,193),(197,361),(448,414),(672,160)]: add("forest-mushrooms",x,y,solid=False)
            for x,y in [(369,251),(445,287),(370,323),(421,352),(255,449),(211,302),(624,352)]: add("forest-flower",x,y,solid=False)
            # El río se marca explícitamente: el motor no infiere colisión del dibujo.
            for y in range(h):
                for x in range(w):
                    if 9<=ground[y*w+x]<=12:
                        collisions.append({"id":next_id,"name":"water","x":x*32,"y":y*32,"width":32,"height":32,"rotation":0,"visible":True});next_id+=1

        spawn = {"id": next_id,"name":"Inicio","x":350,"y":390,"point":True,"rotation":0,"visible":True}
        tile_layer={"id":1,"name":"Suelo","type":"tilelayer","x":0,"y":0,"width":w,"height":h,"opacity":1,"visible":True,"data":ground}
        layers=[tile_layer]
        for lid,name,items,visible in [(2,"Escenario",decorations,True),(3,"Interacciones",interactions,False),(4,"Colisiones",collisions,False),(5,"Inicio",[spawn],False)]:
            layers.append({"id":lid,"name":name,"type":"objectgroup","draworder":"topdown","x":0,"y":0,"opacity":1,"visible":visible,"objects":items})
        tiled_map={"type":"map","version":"1.10","tiledversion":"1.12.2","orientation":"orthogonal","renderorder":"right-down",
                   "infinite":False,"width":w,"height":h,"tilewidth":tile,"tileheight":tile,"nextlayerid":6,"nextobjectid":next_id+1,
                   "backgroundcolor":"#142630","compressionlevel":-1,"layers":layers,
                   "tilesets":[{"firstgid":1,"source":f"../tilesets/{sid}.tsj"},{"firstgid":100,"source":"../tilesets/objects.tsj"}],
                   "properties":props(world=sid,subject=scene["subject"],objective=scene["objective"],mechanic=scene["mechanic"])}
        write_json(target / f"maps/{sid}.tmj",tiled_map)
        manifest["worlds"].append({**scene,"map":f"maps/{sid}.tmj","preview":f"previews/{sid}.png"})
    write_json(target / "manifest.json",manifest)
    write_json(target / "MindCrafted.tiled-project",{"automappingRulesFile":"","commands":[],"extensionsPath":"extensions","folders":["maps","tilesets","art"],"propertyTypes":[]})
    write_json(target / "MindCrafted.world",{"type":"world","onlyShowAdjacentMaps":False,"maps":[{"fileName":f"maps/{s['id']}.tmj","x":i*832,"y":0,"width":768,"height":512} for i,s in enumerate(SCENES)]})
    return manifest


def find_aseprite(explicit: str | None) -> str:
    candidates=[explicit,os.environ.get("ASEPRITE_BIN"),shutil.which("aseprite"),str(Path.home()/"aseprite/build/bin/aseprite")]
    for item in candidates:
        if item and Path(item).is_file(): return str(Path(item).resolve())
    raise SystemExit("No se encontró Aseprite. Usa --aseprite /ruta/al/ejecutable.")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aseprite")
    parser.add_argument("--replace-art",action="store_true",help="Regenerar originales; sustituye los cambios manuales en art/.")
    parser.add_argument("--output",type=Path,default=ROOT,help="Carpeta de salida alternativa para construir sin tocar los originales.")
    args=parser.parse_args()
    target=args.output.resolve();target.mkdir(parents=True,exist_ok=True)
    if (target/"art/source").exists() and not args.replace_art:
        raise SystemExit("Ya existen fuentes Aseprite. Usa --output con una carpeta nueva o --replace-art para regenerarlas explícitamente.")
    executable=find_aseprite(args.aseprite)
    with tempfile.TemporaryDirectory(prefix=".art-build-",dir=target) as tmp:
        staging=Path(tmp)
        for folder in ("source","exports","palettes"): (staging/folder).mkdir()
        subprocess.run([executable,"--batch","--script-param",f"output={staging}","--script",str(ROOT/"scripts/draw_assets.lua")],check=True)
        catalog=json.loads((staging/"catalog.json").read_text())
        if not catalog or not all((staging/"source"/(a["id"]+".aseprite")).is_file() for a in catalog):
            raise SystemExit("La generación no produjo todos los originales.")
        shutil.copytree(staging,target/"art",dirs_exist_ok=True)
    generate_maps(catalog,target)
    (target/"previews").mkdir(exist_ok=True)
    print(f"Listo: {len(catalog)} recursos y 3 mundos en {target}")


if __name__=="__main__": main()
