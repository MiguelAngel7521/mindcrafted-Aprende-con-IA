import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from mindcrafted.generator.world_demo import SOURCE, demo_blueprint
from mindcrafted.generator.world_package import make_package, render_html
from mindcrafted.generator.world_pipeline import generate_campaign


def parse(raw, label=""):
    return json.loads(raw)


def test_invalid_candidates_never_reach_judge_or_publish(tmp_path):
    calls = []

    async def model(prompt, system, **kwargs):
        calls.append(kwargs["step"])
        blueprint = demo_blueprint()
        blueprint["puzzles"][0]["mechanics"]["archetype"] = "multiple_choice"
        return json.dumps(blueprint)

    with pytest.raises(ValueError, match="tres candidatos"):
        asyncio.run(generate_campaign(SOURCE, tmp_path, generate=model, parse_json=parse))
    assert calls == ["world_blueprint"] * 3
    assert not list(tmp_path.iterdir())


def test_content_cannot_inject_executable_html(world_spec):
    world_spec["dialogues"][0]["lines"][0]["text"] = '</script><script>window.injected=true</script>'
    html = render_html(make_package(world_spec, SOURCE))
    assert '</script><script>window.injected=true</script>' not in html
    assert '\\u003c/script\\u003e' in html
    assert "eval(" not in html
    assert "new Function" not in html


def test_schema_export_matches_runtime_contract():
    from mindcrafted.generator.world_schema import WORLD_SCHEMA
    path = Path(__file__).resolve().parents[1] / "mindcrafted/engine/world/world-v2.schema.json"
    assert json.loads(path.read_text()) == WORLD_SCHEMA


def test_default_generation_dispatches_to_world(monkeypatch, tmp_path):
    from mindcrafted.generator import pipeline, world_pipeline
    received = {}

    async def campaign(source, out, **kwargs):
        received.update(source=source, out=out, **kwargs)
        return "world/index.html"

    monkeypatch.setattr(world_pipeline, "generate_campaign", campaign)
    assert asyncio.run(pipeline.generate_game("Redes", str(tmp_path), source_text=SOURCE, chunk_id="chunk-1")) == "world/index.html"
    assert received["source"] == SOURCE
    assert received["chunk_id"] == "chunk-1"
    assert callable(received["generate"]) and callable(received["parse_json"])


def test_explicit_legacy_mode_remains_available(monkeypatch, tmp_path):
    from mindcrafted.generator import pipeline

    async def legacy(*args, **kwargs):
        return "legacy/index.html"

    monkeypatch.setattr(pipeline, "_generate_fast_game", legacy)
    assert asyncio.run(pipeline.generate_game("Redes", str(tmp_path), world_native=False)) == "legacy/index.html"


def test_world_course_links_and_package_endpoint(world_spec, monkeypatch, tmp_path):
    import httpx
    from mindcrafted import server
    from mindcrafted.generator.course_pipeline import _patch_game_html
    package = make_package(world_spec, SOURCE, "region_a")
    directory = tmp_path / "sample/games/region_a"
    directory.mkdir(parents=True)
    (directory / "game.pkg.json").write_text(json.dumps(package))
    (directory / "index.html").write_text(render_html(package))
    manifest = {"games": [{"chunk_id": "region_a", "status": "success"}, {"chunk_id": "failed", "status": "failed"}, {"chunk_id": "region_b", "status": "success"}]}
    (tmp_path / "sample/course-manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(server, "COURSES_DIR", tmp_path)
    monkeypatch.setattr(server, "REGISTRY", tmp_path / "courses.json")
    _patch_game_html(str(directory / "index.html"), str(directory), str(tmp_path), course_id="sample", next_game_url="/play?course=sample&game=region_b")
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
            response = await client.get("/play?course=sample&game=region_a")
            assert response.status_code == 200
            assert '/engine/world/core.js' in response.text
            assert '/engine/adventure/encounters.js' not in response.text
            data = (await client.get("/api/play/sample/region_a/package")).json()
            assert data["config"]["nextGameUrl"].endswith("game=region_b")
            assert data["config"]["generationMode"] == "world"
            assert data["world"]["version"] == 2
    asyncio.run(check())
    written = json.loads((directory / "game.pkg.json").read_text())
    assert written["config"]["courseId"] == "sample"


def test_public_generation_api_keeps_its_job_contract(monkeypatch, tmp_path):
    import httpx
    from mindcrafted import server
    received = []
    async def run(jid, content, **kwargs):
        received.append((jid, content))
    monkeypatch.setattr(server, "_run_generation", run)
    monkeypatch.setattr(server, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(server, "COURSES_DIR", tmp_path)
    monkeypatch.setattr(server, "REGISTRY", tmp_path / "courses.json")
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
            result = await client.post("/api/generate", json={"course_id": "world_contract", "api_key": "offline-test-key", "content": {
                "course": {"title":"Redes", "gameplay":"world"}, "chunks": [{"id":"chunk-1","title":"Routing","content":SOURCE}]}})
            assert result.status_code == 200, result.text
            assert set(result.json()) == {"job_id", "course_id"}
    asyncio.run(check())
    assert received and received[0][1]["course"]["gameplay"] == "world"
