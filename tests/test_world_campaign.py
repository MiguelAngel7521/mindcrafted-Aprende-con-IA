import asyncio
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_campaign import assemble_campaign, write_campaign
from mindcrafted.generator.world_demo import SOURCE, boss_blueprint, demo_blueprint
from mindcrafted.generator.world_package import make_package


@pytest.fixture(scope="module")
def campaign_packages():
    worlds = [compile_world(demo_blueprint(), SOURCE),
              compile_world(boss_blueprint(), SOURCE, difficulty="hard", prior_skills=["network.load_balance", "network.routing"])]
    packages = [make_package(world, SOURCE, f"lesson.{index + 1}") for index, world in enumerate(worlds)]
    for package in packages:
        package["developmentDemo"] = True
    return packages


def test_boss_combines_learned_rules_and_has_a_nontrivial_solution(campaign_packages):
    world = campaign_packages[-1]["world"]
    report = validate_world(world, SOURCE)
    assert report["ok"], report["errors"]
    solution = report["solutions"]["relay_boss"]
    assert solution["steps"] >= 6
    assert 0 < solution["randomSuccessProbability"] <= 0.1
    assert world["puzzles"][0]["success"]["xp"] == 200
    with pytest.raises(ValueError, match="previamente"):
        compile_world(boss_blueprint(), SOURCE)
    with pytest.raises(ValueError, match="previas"):
        assemble_campaign([campaign_packages[-1]], development=True)


@pytest.mark.parametrize("mutation", [
    lambda p: p[0]["world"].update(title="Alterado después del gate"),
    lambda p: p[1]["config"].update(chunkId=p[0]["config"]["chunkId"]),
    lambda p: p[0]["config"].update(chunkId="../escape"),
    lambda p: p[0]["knowledgeGraph"]["source"].update(sha256="0" * 64),
    lambda p: p[0].update(developmentDemo=False),
])
def test_campaign_rejects_corrupt_or_unapproved_regions(campaign_packages, mutation):
    packages = deepcopy(campaign_packages)
    mutation(packages)
    with pytest.raises(ValueError):
        assemble_campaign(packages, development=True)


def test_development_export_cannot_be_published_as_ai_approved(campaign_packages):
    with pytest.raises(ValueError, match="QualityGate"):
        assemble_campaign(campaign_packages)


@pytest.fixture(scope="module")
def campaign_export(campaign_packages, tmp_path_factory):
    root = tmp_path_factory.mktemp("campaign")
    package = assemble_campaign(campaign_packages, "sample", development=True)
    manifest = write_campaign(package, root / "sample/campaign")
    return root, manifest


def test_real_browser_transitions_stay_on_one_canvas_and_reload(campaign_export):
    root, manifest = campaign_export
    package = json.loads((root / "sample/campaign/game.pkg.json").read_text())
    assert package["campaignChecks"] == {"ok": True, "steps": package["campaignChecks"]["steps"], "reload": True, "mobile": True, "regions": 2, "recovery": True}
    assert manifest["format"] == "mindcrafted-campaign" and manifest["version"] == 2
    assert len(manifest["regions"]) == 2
    assert (root / "sample/campaign/knowledge.json").exists()
    assert '"debug": true' not in (root / "sample/campaign/index.html").read_text()


def test_campaign_api_and_existing_play_links(campaign_export, campaign_packages, monkeypatch):
    from mindcrafted import server
    root, _ = campaign_export
    monkeypatch.setattr(server, "COURSES_DIR", root)
    monkeypatch.setattr(server, "REGISTRY", root / "courses.json")
    game_dir = root / "sample/games/lesson.1"
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "game.pkg.json").write_text(json.dumps(campaign_packages[0]))

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
            page = await client.get("/play?course=sample")
            assert page.status_code == 200 and "/engine/world/campaign.js" in page.text
            manifest = await client.get("/api/v2/campaigns/sample")
            assert manifest.status_code == 200 and len(manifest.json()["regions"]) == 2
            package = await client.get("/api/v2/campaigns/sample/package")
            assert package.status_code == 200
            existing = await client.get("/api/play/sample/lesson.1/package")
            assert existing.json()["campaign"] == package.json()["campaign"]
            assert (await client.get("/api/v2/campaigns/missing/package")).status_code == 404
    asyncio.run(check())


def test_campaign_schema_export_matches_python_contract():
    from mindcrafted.generator.world_schema import CAMPAIGN_SCHEMA
    path = Path(__file__).resolve().parents[1] / "mindcrafted/engine/world/campaign-v2.schema.json"
    assert json.loads(path.read_text()) == CAMPAIGN_SCHEMA


def test_course_generation_transfers_knowledge_and_publishes_continuous_boss(monkeypatch, tmp_path):
    from mindcrafted.generator import course_pipeline
    from mindcrafted.generator.world_pipeline import generate_campaign
    requests = []

    async def model(prompt, system, **kwargs):
        request = json.loads(prompt)
        if kwargs["step"] == "world_blueprint":
            requests.append(request)
            return json.dumps(boss_blueprint() if request["progression"] == "boss" else demo_blueprint())
        assert all(request["tests"].values())
        return json.dumps({"approved": True, "scores": {k: 23 for k in ("embodiedLearning", "worldIntegration", "interactionQuality", "technicalSolvability")}, "issues": []})

    async def generate(topic, output_dir, **kwargs):
        return await generate_campaign(kwargs["source_text"], output_dir, generate=model, parse_json=lambda raw, label: json.loads(raw),
                                       chunk_id=kwargs["chunk_id"], title=kwargs["forced_title"],
                                       previous_context=kwargs["world_learning_context"], require_boss=kwargs["world_boss"])

    monkeypatch.setattr(course_pipeline, "generate_game", generate)
    content_path = tmp_path / "source.json"
    content_path.write_text(json.dumps({"course": {"title": "Redes", "gameplay": "world"},
                                      "chunks": [{"id": "routing", "title": "Redes", "content": SOURCE},
                                                 {"id": "relay", "title": "Transferencia", "content": SOURCE}]}))
    manifest = asyncio.run(course_pipeline.generate_course(str(content_path), str(tmp_path / "course")))
    assert all(g["status"] == "success" for g in manifest["games"]), manifest
    assert manifest["boss_status"] == "complete"
    assert len(manifest["campaign"]["regions"]) == 2
    assert requests[0]["progression"] == "introduction"
    assert requests[1]["progression"] == "boss"
    assert set(requests[1]["priorKnowledge"]["skills"]) == {"network.routing", "network.load_balance"}
    package = json.loads((tmp_path / "course/campaign/game.pkg.json").read_text())
    assert package["campaignChecks"]["ok"] and package["campaignChecks"]["recovery"]
    assert package["campaign"]["regions"][-1]["world"]["puzzles"][-1]["role"] == "boss"
    assert all(report["approved"] for report in package["regionQuality"])


@pytest.mark.parametrize("invalid", [".", "..", "../outside", "a" * 129, [], {}, 123])
def test_course_and_lesson_paths_reject_ambiguous_ids(invalid):
    from fastapi import HTTPException
    from mindcrafted import server
    for validator in (server._safe_course_id, server._safe_chunk_id):
        with pytest.raises(HTTPException):
            validator(invalid)
