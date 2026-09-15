"""Walk and connect physical components on the persistent map, including reload."""
import json
import shutil

import pytest
from playwright.sync_api import sync_playwright

from mindcrafted.generator.node_connect_demo import SOURCE, blueprint
from mindcrafted.generator.world import compile_world
from mindcrafted.generator.world_continuity import assert_world_continuity, install_continuity_guard
from mindcrafted.generator.world_package import make_package, render_html
from test_world_native_routing import Player, routing_page


def test_region_transition_keeps_previous_continuity_failures(routing_page):
    page, _ = routing_page
    page.evaluate("document.body.append(document.createElement('canvas'))")
    with pytest.raises(AssertionError, match="Second game canvas"):
        assert_world_continuity(page, same_engine=True)
    page.evaluate("document.querySelector('canvas:last-of-type:not(#world)').remove()")
    page.evaluate("__WORLD_CONTINUITY__.enterRegion()")
    with pytest.raises(AssertionError, match="Second game canvas"):
        assert_world_continuity(page, same_engine=True)


def test_node_connect_keyboard_failure_partial_save_world_consequence_and_reload(tmp_path):
    world = compile_world(blueprint(), SOURCE, difficulty="hard")
    package = make_package(world, SOURCE)
    package["config"]["debug"] = True
    html = render_html(package)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which("chromium") or shutil.which("chromium-browser"))
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 1050}, reduced_motion="reduce")
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route):
                if route.request.url == "http://mindcrafted.test/":
                    route.fulfill(body=html, content_type="text/html")
                else:
                    errors.append("Unexpected request: " + route.request.url)
                    route.abort()

            page.route("**/*", serve)
            page.goto("http://mindcrafted.test/")
            page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
            install_continuity_guard(page)
            player = Player(page, world)

            def touch(node):
                player.approach("layers_" + node)
                player.press("e")

            def connect(source, target):
                touch(source)
                assert player.state()["puzzles"]["layers"]["selectedNode"] == source
                touch(target)
                assert player.state()["puzzles"]["layers"]["selectedNode"] is None

            player.press("ArrowLeft")
            player.press("ArrowLeft")
            assert player.state()["player"]["x"] == 1
            touch("mentor")
            intro = page.locator("#dialogue-text").inner_text()
            assert intro != world["puzzles"][0]["hint"]
            player.finish_dialogue()
            assert player.state()["quests"]["layers_quest"] == "active"
            connect("UI", "API")
            partial = player.state()["puzzles"]["layers"]
            assert partial["connections"] == ["UI_API"]
            assert player.pixel("layers_API") == [115, 186, 188]
            page.screenshot(path=str(tmp_path / "node-connect-partial.png"), full_page=True)
            bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
            player.reload()
            assert player.state()["puzzles"]["layers"]["connections"] == partial["connections"]
            assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
            connect("UI", "API")  # Explicit disconnect, before submitting.
            assert player.state()["puzzles"]["layers"]["connections"] == []
            connect("UI", "DB")  # A real cable that violates the academic layering rule.
            touch("console")
            failure = player.state()["puzzles"]["layers"]
            assert failure["attempts"] == failure["errors"] == 1
            assert not failure["solved"] and failure["connections"] == []
            assert failure["effect"]["invalidEdges"] == ["UI_DB"]
            assert player.pixel("layers_console") == [238, 151, 122]
            assert not player.state()["flags"].get("layers_restored")
            assert player.state()["xp"] == 0
            page.screenshot(path=str(tmp_path / "node-connect-failure.png"), full_page=True)
            bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
            assert {r["skillId"]: r["correct"] for r in bkt["records"]}["software.layers"] == 0
            player.reload()
            assert player.state()["puzzles"]["layers"]["effect"] == failure["effect"]
            assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
            player.press("h")
            assert page.locator("#feedback").inner_text() != world["puzzles"][0]["hint"]
            player.press("r")
            assert player.state()["puzzles"]["layers"]["effect"] is None
            assert player.pixel("layers_console") == [48, 73, 79]
            connect("UI", "ALT")  # Use the other valid solution, not the solver's first one.
            player.reload()
            assert player.state()["puzzles"]["layers"]["connections"] == ["UI_ALT"]
            connect("ALT", "REPO")
            connect("REPO", "DB")
            touch("console")
            solved = player.state()
            assert solved["puzzles"]["layers"]["solved"]
            assert solved["flags"]["layers_restored"] and solved["quests"]["layers_quest"] == "complete"
            assert solved["xp"] == 75 and len(solved["inventory"]) == 1
            assert player.pixel("layers_console") == [134, 217, 171]
            player.finish_dialogue()
            touch("mentor")
            assert player.state()["dialogue"]["id"] == "layers_after"
            assert page.locator("#dialogue-text").inner_text() != intro
            player.finish_dialogue()
            assert player.state()["flags"]["layers_understood"]
            bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
            assert len(bkt["records"]) == 3
            for record in bkt["records"]:
                assert record["attempts"] == 2
                assert record["lastObservations"]["hintsUsed"] == record["lastObservations"]["restarts"] == 1
                assert record["lastObservations"]["solutionSteps"] >= 7
            page.screenshot(path=str(tmp_path / "node-connect-restored.png"), full_page=True)
            player.walk({(20, 9)})
            assert player.pixel("layers_gate", 5, 8) == [127, 207, 159]
            player.press("ArrowRight")
            player.press("ArrowRight")
            assert player.state()["player"]["x"] == 22
            saved = player.state()
            player.reload()
            assert player.state() == saved
            assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
            touch("console")
            player.press("r")
            assert player.state()["xp"] == 75
            assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
            # Responsive controls use the same world renderer after the entire journey.
            page.set_viewport_size({"width": 390, "height": 844})
            player.check()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(tmp_path / "node-connect-mobile.png"), full_page=True)
            (tmp_path / "node-connect-e2e.json").write_text(json.dumps({
                "ok": True, "partialReload": True, "failureReload": True, "solvedReload": True,
                "disconnect": True, "reset": True, "sameCanvas": True, "sameEngine": True,
                "worldConsequence": True, "bkt": bkt}, ensure_ascii=False, indent=2))
            assert not errors, errors
        finally:
            browser.close()
