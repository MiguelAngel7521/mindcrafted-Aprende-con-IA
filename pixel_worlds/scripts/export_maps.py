#!/usr/bin/env python3
"""Valida y exporta los mapas actuales con Tiled. No regenera arte ni mapas fuente."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    args=parser.parse_args();root=args.root.resolve()
    tiled=shutil.which("tiled");renderer=shutil.which("tmxrasterizer")
    if not tiled or not renderer:raise SystemExit("Se necesitan tiled y tmxrasterizer en PATH.")
    (root/"previews").mkdir(exist_ok=True)
    manifest=json.loads((root/"manifest.json").read_text())
    for world in manifest["worlds"]:
        path=root/world["map"]
        subprocess.run([tiled,"--export-map",str(path),str(path.with_suffix('.tmx'))],check=True)
        subprocess.run([renderer,"--no-smoothing",str(path),str(root/world["preview"])],check=True)
        print(f"Exportado: {world['title']}")
    print("Exportaciones terminadas. En Linux sin sesión gráfica puede requerirse xvfb-run.")
