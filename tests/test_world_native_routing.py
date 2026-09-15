"""Public World V2 player: real keyboard inputs, rendered consequences and reload."""
import asyncio
import json
import re
import shutil
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.sync_api import sync_playwright

from mindcrafted.generator.world import DIRECTIONS, compile_world, find_path
from mindcrafted.generator.world_continuity import assert_world_continuity, install_continuity_guard
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint
from mindcrafted.generator.world_package import make_package
from mindcrafted.generator.world_solver import route_options


@pytest.fixture
def routing_page(tmp_path, monkeypatch):
    from mindcrafted import server

    world = compile_world(demo_blueprint(), SOURCE, difficulty="hard")
    package = make_package(world, SOURCE, "routing")
    package["config"]["debug"] = True
    directory = tmp_path / "native/games/routing"
    directory.mkdir(parents=True)
    (directory / "game.pkg.json").write_text(json.dumps(package))
    monkeypatch.setattr(server, "COURSES_DIR", tmp_path)
    monkeypatch.setattr(server, "REGISTRY", tmp_path / "courses.json")
    url = "http://mindcrafted.test/play?course=native&game=routing"

    async def responses():
        # Use actual ASGI dispatch/static assets, isolated from courses and the network.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://mindcrafted.test") as client:
            player = await client.get(url)
            paths = re.findall(r'(?:src|href)="(/[^\"]+)"', player.text)
            paths += ["/api/play/native/routing/package", "/assets/fonts/PixelifySans.ttf"]
            result = {"/play?course=native&game=routing": player}
            for path in set(paths):
                result[path] = await client.get(path)
            assert all(response.status_code == 200 for response in result.values())
            assert "/engine/world/core.js" in player.text
            return result

    resources = asyncio.run(responses())
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which("chromium") or shutil.which("chromium-browser"))
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 1050}, reduced_motion="reduce")
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route):
                parsed = urlsplit(route.request.url)
                path = parsed.path + ("?" + parsed.query if parsed.query else "")
                if parsed.netloc != "mindcrafted.test" or path not in resources:
                    errors.append("Unexpected request: " + route.request.url)
                    route.abort()
                    return
                response = resources[path]
                route.fulfill(body=response.content, content_type=response.headers["content-type"])

            page.route("**/*", serve)
            page.goto(url)
            page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
            install_continuity_guard(page)
            yield page, world
            assert not errors
        finally:
            browser.close()


class Player:
    def __init__(self, page, world):
        self.page, self.region = page, world["regions"][0]
        self.entities = {entity["id"]: entity for entity in self.region["entities"]}

    def state(self):
        return self.page.evaluate("__MINDCRAFTED_TEST__.getState()")

    def check(self):
        self.page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        assert_world_continuity(self.page, same_engine=True, pixels=True)

    def press(self, key):
        self.page.keyboard.press(key)
        self.check()

    def walk(self, targets):
        state = self.state()
        obstacles = {(e["x"], e["y"]) for e in self.entities.values()
                     if e["type"] not in ("goal", "exit") and not (e["type"] == "door" and state["flags"].get(e["requiresFlag"]))}
        _, path = find_path(self.region, (state["player"]["x"], state["player"]["y"]), targets, obstacles)
        for action in path:
            before = self.state()["player"]
            self.press("Arrow" + action["direction"].capitalize())
            dx, dy = DIRECTIONS[action["direction"]]
            after = self.state()["player"]
            assert (after["x"], after["y"]) == (before["x"] + dx, before["y"] + dy)

    def approach(self, entity_id):
        entity = self.entities[entity_id]
        self.walk({(entity["x"] + dx, entity["y"] + dy) for dx, dy in DIRECTIONS.values()})
        assert self.page.evaluate("worldEngine.nearby()[0].id") == entity_id

    def finish_dialogue(self):
        for _ in range(8):
            if not self.state()["dialogue"]:
                return
            self.press("e")
        assert not self.state()["dialogue"]

    def wire(self, mechanics, routes):
        options = route_options(mechanics)
        for node, target in routes.items():
            self.approach("routing_" + node)
            for _ in range(options[node].index(target) + 1):
                self.press("e")
            assert self.state()["puzzles"]["routing"]["routes"][node] == target

    def pixel(self, entity_id, x=18, y=14):
        return self.page.evaluate("""({id, x, y}) => {
          const entity = worldEngine.entities.get(id), {camera, cell} = __MINDCRAFTED_TEST__.getView();
          return Array.from(document.getElementById('world').getContext('2d').getImageData(
            Math.round((entity.x - camera.x) * cell) + x, Math.round((entity.y - camera.y) * cell) + y, 1, 1).data).slice(0, 3);
        }""", {"id": entity_id, "x": x, "y": y})

    def reload(self):
        self.check()
        self.page.reload()
        self.page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
        install_continuity_guard(self.page)
        self.check()


def test_npc_quest_failure_recovery_solution_world_reaction_and_reload(routing_page, tmp_path):
    page, world = routing_page
    player = Player(page, world)
    puzzle = world["puzzles"][0]
    bad = {"A": "B", "E": "B", "F": "B", "G": "B", "B": "D", "C": "D"}
    good = dict(bad, F="C", G="C")
    player.press("ArrowLeft")
    player.press("ArrowLeft")
    assert player.state()["player"]["x"] == 1  # Border collision.
    player.approach("routing_mentor")
    player.press("e")
    assert player.state()["dialogue"]["id"] == "routing_intro"
    introduction = page.locator("#dialogue-text").inner_text()
    assert introduction != puzzle["hint"]
    position = player.state()["player"]
    player.press("ArrowDown")
    assert player.state()["player"] == position
    player.finish_dialogue()
    assert player.state()["quests"]["routing_quest"] == "active"
    player.approach("routing_console")
    assert player.pixel("routing_console") == [48, 73, 79]
    # The closed route really blocks walking, not just a UI status.
    player.walk({(20, 9)})
    player.press("ArrowRight")
    assert player.state()["player"]["x"] == 20
    assert player.pixel("routing_gate", 5, 8) == [73, 103, 118]
    player.wire(puzzle["mechanics"], bad)
    player.approach("routing_console")
    player.press("e")
    failure = player.state()["puzzles"]["routing"]
    assert failure["attempts"] == failure["errors"] == failure["congestionEvents"] == 1
    assert failure["routes"] == {} and failure["effect"]["routes"] == bad
    assert failure["effect"]["congested"] == ["B"]
    assert failure["invalidRoutes"] == 4 and failure["correctRoutes"] == 0
    assert not player.state()["flags"].get("routing_restored")
    assert player.pixel("routing_console") == [238, 151, 122]
    page.screenshot(path=str(tmp_path / "network-failure.png"), full_page=True)
    failure_bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
    player.reload()
    assert player.pixel("routing_console") == [238, 151, 122]
    assert player.state()["puzzles"]["routing"]["effect"] == failure["effect"]
    assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == failure_bkt
    player.press("h")
    assert page.locator("#feedback").inner_text() != puzzle["hint"]
    player.press("r")
    assert player.state()["puzzles"]["routing"]["effect"] is None
    assert player.pixel("routing_console") == [48, 73, 79]
    player.wire(puzzle["mechanics"], good)
    player.approach("routing_console")
    player.press("e")
    solved = player.state()
    assert solved["puzzles"]["routing"]["solved"]
    assert solved["flags"]["routing_restored"]
    assert solved["quests"]["routing_quest"] == "complete"
    assert player.pixel("routing_console") == [134, 217, 171]
    assert solved["xp"] == puzzle["success"]["xp"] and len(solved["inventory"]) == 1
    player.finish_dialogue()
    player.approach("routing_mentor")
    player.press("e")
    assert player.state()["dialogue"]["id"] == "routing_after"
    assert page.locator("#dialogue-text").inner_text() != introduction
    player.finish_dialogue()
    assert player.state()["flags"]["routing_understood"]
    bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
    assert len(bkt["records"]) == 2
    for record in bkt["records"]:
        assert record["attempts"] == 2
        observed = record["lastObservations"]
        assert observed["correctRoutes"] == observed["invalidRoutes"] == 4
        assert observed["congestionEvents"] == observed["hintsUsed"] == observed["restarts"] == 1
    player.walk({(20, 9)})
    assert player.pixel("routing_gate", 5, 8) == [127, 207, 159]
    player.press("ArrowRight")
    player.press("ArrowRight")
    assert player.state()["player"]["x"] == 22
    saved = player.state()
    player.reload()
    assert player.state() == saved
    assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
    player.approach("routing_console")
    assert player.pixel("routing_console") == [134, 217, 171]
    player.press("e")
    player.press("r")
    assert player.state()["xp"] == solved["xp"]
    assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
    page.screenshot(path=str(tmp_path / "network-restored.png"), full_page=True)


@pytest.mark.parametrize("regression", ["iframe", "overlay", "canvas", "hidden", "repaint"])
def test_continuity_guard_rejects_separate_encounters_even_when_removed(routing_page, regression):
    page, _ = routing_page
    # These mutations simulate regressions; the playable E2E above only uses keys.
    page.evaluate("""kind => {
      const canvas = document.getElementById('world');
      if (kind === 'hidden') canvas.hidden = true;
      else if (kind === 'repaint') {
        const ctx = canvas.getContext('2d'); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, canvas.width, canvas.height);
        __WORLD_CONTINUITY__.check({pixels: true});
      } else {
        const node = document.createElement(kind === 'overlay' ? 'div' : kind);
        if (kind === 'overlay') node.id = 'mini-game-overlay';
        document.body.append(node); node.remove();
      }
    }""", regression)
    with pytest.raises(AssertionError, match="WORLD_INTEGRATION_ERROR"):
        assert_world_continuity(page, same_engine=True)
