#!/usr/bin/env python3
"""Sirve únicamente pixel_worlds/ en localhost; no expone .env ni los cursos."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,".mjs":"text/javascript",".tmj":"application/json",".tsj":"application/json"}

    def do_GET(self):
        if self.path=="/":
            self.send_response(302);self.send_header("Location","/web/");self.end_headers();return
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control","no-cache")
        self.send_header("X-Content-Type-Options","nosniff")
        super().end_headers()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--port",type=int,default=8011);args=parser.parse_args()
    try:
        server=ThreadingHTTPServer(("127.0.0.1",args.port),partial(Handler,directory=str(ROOT)))
    except OSError as error:
        raise SystemExit(f"No se pudo abrir el puerto {args.port}: {error}. Prueba --port 8012.")
    print(f"Atlas de mundos: http://127.0.0.1:{args.port}/web/",flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
