"""Servidor aislado para pruebas del navegador. IA simulada, sin llamadas externas.
Ejecutar desde la raíz: .venv/bin/python tests/serve_practice_fixture.py
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from practice_fixtures import SOURCES, fixture, technology_fixture


def main():
    with tempfile.TemporaryDirectory(prefix='mindcrafted-browser-') as tmp:
        os.environ['MINDCRAFTED_HOME'] = tmp
        os.environ['API_KEY'] = 'fixture-only-not-a-real-key'
        os.environ['API_BASE_URL'] = 'https://example.com/v1'
        assets = Path(tmp)/'assets/fonts'
        assets.mkdir(parents=True)
        shutil.copyfile(ROOT/'assets/fonts/PixelifySans.ttf', assets/'PixelifySans.ttf')
        from mindcrafted.generator import pipeline
        async def fake_generate(prompt, system, **kwargs):
            if 'material insuficiente' in prompt: return '{}'
            if 'En esta red didáctica' in prompt: return json.dumps(technology_fixture(), ensure_ascii=False)
            world = 'biology' if 'germinación' in prompt else 'laboratory' if 'ley de Ohm' in prompt else 'mathematics'
            return json.dumps(fixture(world), ensure_ascii=False)
        pipeline._bind_api_config = lambda *args, **kwargs: fake_generate
        from mindcrafted.server import app
        import uvicorn
        print('PRUEBA AISLADA: IA simulada; datos temporales en '+tmp, flush=True)
        uvicorn.run(app, host='127.0.0.1', port=8022, log_level='warning')

if __name__ == '__main__': main()
