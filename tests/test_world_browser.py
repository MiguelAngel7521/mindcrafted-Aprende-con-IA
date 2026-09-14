from mindcrafted.generator.world import validate_world
from mindcrafted.generator.world_demo import SOURCE
from mindcrafted.generator.world_package import browser_probe, make_package


def test_playwright_walkthrough_reload_and_mobile(world_spec, tmp_path):
    report = validate_world(world_spec, SOURCE)
    result = browser_probe(make_package(world_spec, SOURCE), report["walkthrough"], screenshot=tmp_path / "world.png")
    assert result["ok"] and result["reload"] and result["mobile"]


def test_generation_repairs_and_publishes_only_after_real_checks(tmp_path):
    import asyncio
    import json
    from mindcrafted.generator.world_demo import demo_blueprint
    from mindcrafted.generator.world_pipeline import generate_campaign
    calls = []

    async def model(prompt, system, **kwargs):
        step = kwargs["step"]
        calls.append(step)
        request = json.loads(prompt)
        if len(calls) == 1:
            return '{"puzzles": []}'
        if step == "world_blueprint":
            assert request["repair"]["errors"]
            return json.dumps(demo_blueprint())
        assert all(request["tests"].values())
        return json.dumps({"approved": True, "scores": {"embodiedLearning":22,"worldIntegration":23,"interactionQuality":22,"technicalSolvability":24}, "issues":[]})

    result = asyncio.run(generate_campaign(SOURCE, str(tmp_path), generate=model, parse_json=lambda raw, label: json.loads(raw), chunk_id="chunk-1", title="Redes"))
    package = json.loads((tmp_path / "game.pkg.json").read_text())
    assert calls == ["world_blueprint", "world_blueprint", "world_judge"]
    assert package["quality"]["approved"] is True
    assert all(package["quality"]["checks"].values())
    assert package["config"]["generationMode"] == "world"
    assert (tmp_path / "campaign/puzzles/routing.json").exists()
    assert (tmp_path / "campaign/regions/main_region.json").exists()
    assert result.endswith("index.html")
