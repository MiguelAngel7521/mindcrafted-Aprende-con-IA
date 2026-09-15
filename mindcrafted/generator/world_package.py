"""Rendering, runtime probes and an all-required publication gate."""

import base64
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from .world import DIRECTIONS, find_path, validate_world, world_hash
from .world_knowledge import build_knowledge_graph
from .world_solver import network_result, route_options
from .world_continuity import assert_world_continuity, install_continuity_guard

ENGINE = Path(__file__).resolve().parents[1] / "engine"
ROOT = ENGINE.parent.parent
CHECKS = ("schema", "worldGraph", "solver", "educational", "runtime", "e2e")
RUBRIC = ("embodiedLearning", "worldIntegration", "interactionQuality", "technicalSolvability")
JUDGE_SCHEMA = {"type": "object", "additionalProperties": False,
                "properties": {"approved": {"type": "boolean"},
                    "scores": {"type": "object", "additionalProperties": False,
                               "properties": {key: {"type": "integer", "minimum": 0, "maximum": 25} for key in RUBRIC},
                               "required": list(RUBRIC)},
                    "issues": {"type": "array", "items": {"type": "string"}}},
                "required": ["approved", "scores", "issues"]}


def make_package(world, source, chunk_id="", title=None):
    sprite = ROOT / "pixel_worlds/art/exports/adventure-explorer-sheet.png"
    sprites = {"player": "data:image/png;base64," + base64.b64encode(sprite.read_bytes()).decode()} if sprite.exists() else {}
    return {"v": 4, "title": title or world["title"], "subtitle": world["introduction"], "total_chapters": len(world["puzzles"]),
            "config": {"generationMode": "world", "locale": "es", "chunkId": chunk_id, "worldHash": world_hash(world),
                       "sourceHash": hashlib.sha256(source.encode()).hexdigest(), "totalChapters": len(world["puzzles"])},
            "format": "mindcrafted-campaign", "version": 2,
            "world": deepcopy(world), "knowledgeGraph": build_knowledge_graph(world, source), "sprites": sprites}


def render_html(package):
    html = (ENGINE / "world/player.html").read_text(encoding="utf-8")
    data = json.dumps(package, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    css = (ENGINE / "world/style.css").read_text()
    font = ROOT / "assets/fonts/PixelifySans.ttf"
    if font.exists():
        css = css.replace("/assets/fonts/PixelifySans.ttf", "data:font/ttf;base64," + base64.b64encode(font.read_bytes()).decode())
    html = html.replace('<link rel="stylesheet" href="/engine/world/style.css">', '<style>' + css + '</style>')
    for script in ("bkt.js", "world/event-bus.js", "world/flag-system.js", "world/quest-system.js",
                   "world/dialogue-system.js", "world/node-connect.js", "world/core.js", "world/campaign.js", "world/runtime.js"):
        code = '<script>' + (ENGINE / script).read_text(encoding="utf-8") + '</script>'
        if script == "world/runtime.js":
            code = '<script id="world-data" type="application/json">' + data + '</script>' + code
        html = html.replace(f'<script src="/engine/{script}"></script>', code)
    return html


def runtime_probe(world, walkthrough):
    node = shutil.which("node")
    if not node:
        raise ValueError("Node es obligatorio para validar el runtime world")
    result = subprocess.run([node, str(ENGINE / "world/probe.cjs")],
                            input=json.dumps({"world": world, "walkthrough": walkthrough}), text=True,
                            capture_output=True, timeout=35)
    if result.returncode:
        raise ValueError("Runtime rechazó el recorrido: " + result.stderr[-2400:])
    return json.loads(result.stdout)


def browser_probe(package, walkthrough, screenshot=None):
    """Actual Playwright keyboard E2E; hermetic routing prevents external requests."""
    from playwright.sync_api import sync_playwright
    keys = {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}
    debug_package = deepcopy(package)
    debug_package["config"]["debug"] = True
    html = render_html(debug_package)
    errors = []
    with sync_playwright() as playwright:
        executable = shutil.which("chromium") or shutil.which("chromium-browser")
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 1050}, reduced_motion="reduce")
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

            def serve(route):
                url = route.request.url
                if url == "http://mindcrafted.test/":
                    route.fulfill(body=html, content_type="text/html")
                elif url.endswith("/assets/fonts/PixelifySans.ttf"):
                    font = ROOT / "assets/fonts/PixelifySans.ttf"
                    route.fulfill(body=font.read_bytes(), content_type="font/ttf")
                else:
                    errors.append("Unexpected request: " + url)
                    route.abort()

            page.route("**/*", serve)
            page.goto("http://mindcrafted.test/")
            page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
            install_continuity_guard(page)
            if screenshot:
                page.screenshot(path=str(screenshot), full_page=True)
            first = page.evaluate("worldEngine.snapshot().player")
            page.keyboard.press("ArrowLeft")
            page.keyboard.press("ArrowLeft")
            assert page.evaluate("worldEngine.state.player.x") == 1, "Collision with map border failed"
            page.keyboard.press("ArrowRight")
            assert page.evaluate("worldEngine.state.player.x") == first["x"]
            recovery = False
            recovered_connections = set()
            for i, action in enumerate(walkthrough):
                assert_world_continuity(page)
                if action["type"] == "region":
                    assert page.evaluate("__MINDCRAFTED_TEST__.getCampaign().currentRegion") == action["index"], "Region transition failed"
                    assert page.locator("canvas").count() == 1
                    page.evaluate("__WORLD_CONTINUITY__.enterRegion()")
                    if screenshot:
                        path = Path(screenshot)
                        page.screenshot(path=str(path.with_stem(path.stem + f"-region-{action['index'] + 1}")), full_page=True)
                    continue
                before = page.evaluate("worldEngine.snapshot().player") if action["type"] == "move" else None
                if action["type"] == "interact":
                    near = page.evaluate("worldEngine.nearby().map(e => e.id)")
                    assert near and near[0] == action["entityId"], f"Step {i}: UI targets {near}, expected {action['entityId']}"
                page.keyboard.press(keys[action["direction"]] if action["type"] == "move" else "e")
                if before:
                    after = page.evaluate("worldEngine.snapshot().player")
                    assert (after["x"], after["y"]) != (before["x"], before["y"]), f"Step {i}: keyboard movement blocked"
                first_puzzle = package["world"]["puzzles"][0]
                if not recovery and first_puzzle["archetype"] == "route_network" and action["type"] == "dialogue" and page.evaluate("id => worldEngine.active(id) && !worldEngine.state.dialogue", first_puzzle["id"]):
                    _probe_route_recovery(page, package["world"], first_puzzle, keys)
                    recovery = True
                if action["type"] == "dialogue":
                    region_index = page.evaluate("__MINDCRAFTED_TEST__.getCampaign()?.currentRegion || 0")
                    current_world = package["campaign"]["regions"][region_index]["world"] if package.get("campaign") else package["world"]
                    for puzzle in current_world["puzzles"]:
                        key = (region_index, puzzle["id"])
                        if puzzle["archetype"] == "node_connect" and key not in recovered_connections and page.evaluate("id => worldEngine.active(id) && !worldEngine.state.dialogue", puzzle["id"]):
                            _probe_connection_recovery(page, current_world, puzzle, keys, screenshot)
                            recovered_connections.add(key)
                            recovery = True
            assert page.evaluate("worldEngine.state.completed"), "E2E did not reach the exit"
            assert_world_continuity(page)
            assert page.locator("#completion").is_visible()
            assert page.locator("canvas").count() == 1
            assert page.locator("#mini-game-overlay, iframe").count() == 0
            completed = page.evaluate("worldEngine.snapshot()")
            page.reload()
            page.wait_for_function("window.worldEngine && worldEngine.state.completed")
            assert page.evaluate("worldEngine.state.xp") == completed["xp"]
            assert page.evaluate("worldEngine.state.inventory") == completed["inventory"]
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile horizontal overflow"
            if screenshot:
                page.screenshot(path=str(Path(screenshot).with_stem(Path(screenshot).stem + "-completed-mobile")), full_page=True)
            assert not errors, "; ".join(errors)
            return {"ok": True, "steps": len(walkthrough), "reload": True, "mobile": True,
                    "regions": len(package.get("campaign", {}).get("regions", [])) or 1, "recovery": recovery}
        finally:
            browser.close()


def _probe_connection_recovery(page, world, puzzle, keys, screenshot=None):
    """Exercise partial persistence and failure/recovery for every node_connect."""
    from .node_connect import simulate

    region = world["regions"][0]
    original = page.evaluate("worldEngine.snapshot()")
    origin = original["player"]
    entities = {entity["id"]: entity for entity in region["entities"]}
    obstacles = {(e["x"], e["y"]) for e in entities.values() if e["type"] not in ("goal", "exit")
                 and not (e["type"] == "door" and original["flags"].get(e["requiresFlag"]))}
    for other in world["puzzles"]:
        for block in original["puzzles"][other["id"]].get("blocks", []):
            obstacles.add((block["x"] + other["world"]["offset"]["x"], block["y"] + other["world"]["offset"]["y"]))

    def walk(targets):
        start = page.evaluate("worldEngine.state.player")
        _, path = find_path(region, (start["x"], start["y"]), targets, obstacles)
        for action in path:
            page.keyboard.press(keys[action["direction"]])
            assert_world_continuity(page, same_engine=True)

    def interact(entity):
        walk({(entity["x"] + dx, entity["y"] + dy) for dx, dy in DIRECTIONS.values()})
        assert page.evaluate("worldEngine.nearby()[0].id") == entity["id"]
        page.keyboard.press("e")
        assert_world_continuity(page, same_engine=True)

    def reload():
        assert_world_continuity(page, same_engine=True)
        page.reload()
        page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
        install_continuity_guard(page)

    edge = next(e for e in puzzle["mechanics"]["edges"] if simulate(puzzle["mechanics"], [e["id"]])["invalidEdges"])
    for node in (edge["source"], edge["target"]):
        interact(next(e for e in entities.values() if e.get("puzzleId") == puzzle["id"] and e.get("controlId") == node))
    partial = page.evaluate("id => worldEngine.state.puzzles[id].connections", puzzle["id"])
    assert partial == [edge["id"]]
    bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
    reload()
    assert page.evaluate("id => worldEngine.state.puzzles[id].connections", puzzle["id"]) == partial
    assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
    interact(entities[puzzle["world"]["anchorEntity"]])
    state = page.evaluate("id => worldEngine.state.puzzles[id]", puzzle["id"])
    assert not state["solved"] and state["attempts"] == state["errors"] == 1
    assert state["connections"] == [] and edge["id"] in state["effect"]["invalidEdges"]
    assert page.evaluate("id => !worldEngine.isOpen(worldEngine.entities.get(id))", puzzle["success"]["openEntity"])
    if screenshot:
        page.screenshot(path=str(Path(screenshot).with_stem(Path(screenshot).stem + "-" + puzzle["id"] + "-failure")), full_page=True)
    bkt = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
    reload()
    assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == bkt
    assert page.evaluate("id => worldEngine.state.puzzles[id].effect", puzzle["id"]) == state["effect"]
    page.keyboard.press("h")
    assert page.locator("#feedback").inner_text() != puzzle["hint"]
    page.keyboard.press("r")
    assert page.evaluate("id => worldEngine.state.puzzles[id].restarts", puzzle["id"]) == 1
    walk({(origin["x"], origin["y"])})


def _probe_route_recovery(page, world, puzzle, keys):
    """Physically wire an invalid network, fail, hint, reset and reload before solving."""
    region = world["regions"][0]
    origin = page.evaluate("worldEngine.snapshot().player")
    obstacles = {(e["x"], e["y"]) for e in region["entities"] if e["type"] not in ("goal", "exit")}
    for other in world["puzzles"]:
        for b in other["mechanics"].get("blocks", []):
            obstacles.add((b["x"] + other["world"]["offset"]["x"], b["y"] + other["world"]["offset"]["y"]))

    def walk(targets):
        start = page.evaluate("worldEngine.snapshot().player")
        _, path = find_path(region, (start["x"], start["y"]), targets, obstacles)
        for action in path:
            page.keyboard.press(keys[action["direction"]])

    options = route_options(puzzle["mechanics"])
    invalid = next(routes for values in product(*options.values())
                   if not network_result(puzzle["mechanics"], routes := dict(zip(options, values)))["ok"])
    for control, target in invalid.items():
        entity = next(e for e in region["entities"] if e.get("puzzleId") == puzzle["id"] and e.get("controlId") == control)
        walk({(entity["x"] + dx, entity["y"] + dy) for dx, dy in DIRECTIONS.values()})
        assert page.evaluate("worldEngine.nearby()[0].id") == entity["id"]
        for _ in range(options[control].index(target) + 1):
            page.keyboard.press("e")
    console = next(e for e in region["entities"] if e["id"] == puzzle["world"]["anchorEntity"])
    walk({(console["x"] + dx, console["y"] + dy) for dx, dy in DIRECTIONS.values()})
    page.keyboard.press("e")
    state = page.evaluate("id => worldEngine.state.puzzles[id]", puzzle["id"])
    assert state["attempts"] == 1 and state["errors"] == 1 and not state["solved"] and state["routes"] == {}
    assert page.evaluate("id => !worldEngine.isOpen(worldEngine.entities.get(id))", puzzle["success"]["openEntity"])
    page.keyboard.press("h")
    assert page.locator("#feedback").inner_text() != puzzle["hint"], "First hint must not reveal the full solution"
    page.keyboard.press("r")
    observations = page.evaluate("__MINDCRAFTED_TEST__.getBKT()")
    assert observations["records"] and any(r["correct"] == 0 for r in observations["records"])
    assert_world_continuity(page, same_engine=True)
    page.reload()
    page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
    install_continuity_guard(page)
    state = page.evaluate("id => worldEngine.state.puzzles[id]", puzzle["id"])
    assert state["attempts"] == 1 and state["hintsUsed"] == 1 and state["restarts"] == 1
    assert page.evaluate("__MINDCRAFTED_TEST__.getBKT()") == observations, "Reload must not duplicate BKT"
    walk({(origin["x"], origin["y"])})


def check_judge(judge):
    if not isinstance(judge, dict) or set(judge) != {"approved", "scores", "issues"}:
        raise ValueError("Formato de juez inválido")
    scores = judge["scores"]
    if not isinstance(scores, dict) or set(scores) != set(RUBRIC):
        raise ValueError("El juez debe evaluar las cuatro categorías")
    if any(type(n) is not int or not 0 <= n <= 25 for n in scores.values()):
        raise ValueError("Cada categoría debe ser un entero entre 0 y 25")
    if type(judge["approved"]) is not bool or not isinstance(judge["issues"], list) or any(not isinstance(issue, str) for issue in judge["issues"]):
        raise ValueError("Veredicto del juez inválido")
    return judge["approved"] and sum(scores.values()) >= 85 and not judge["issues"]


def quality_gate(world, source, *, judge=None, run_probes=True, screenshot=None):
    report = validate_world(world, source)
    checks = dict(report["checks"], runtime=False, e2e=False)
    result = {"approved": False, "checks": checks, "errors": list(report["errors"]),
              "worldHash": world_hash(world), "judge": judge, "solutions": report["solutions"]}
    if report["ok"] and run_probes:
        try:
            result["runtime"] = runtime_probe(world, report["walkthrough"])
            checks["runtime"] = result["runtime"]["ok"] is True
            result["e2e"] = browser_probe(make_package(world, source), report["walkthrough"], screenshot)
            checks["e2e"] = result["e2e"]["ok"] is True
        except Exception as error:
            result["errors"].append(str(error))
    if judge is not None:
        try:
            result["approved"] = check_judge(judge) and all(checks.get(key) is True for key in CHECKS) and not result["errors"]
        except ValueError as error:
            result["errors"].append(str(error))
    return result


def write_world_package(package, source, report, output_dir):
    world = package["world"]
    if not (report.get("approved") is True and report.get("worldHash") == world_hash(world)
            and all(report.get("checks", {}).get(k) is True for k in CHECKS)
            and check_judge(report.get("judge")) and not report.get("errors")):
        raise ValueError("QualityGate.approved debe ser true antes de publicar")
    # Recheck data after the asynchronous judge; reject changed candidates.
    if not validate_world(world, source)["ok"]:
        raise ValueError("El candidato cambió después de validarse")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    final = deepcopy(package)
    final["knowledgeGraph"] = build_knowledge_graph(world, source)
    final["quality"] = deepcopy(report)
    files = {"game.pkg.json": json.dumps(final, ensure_ascii=False, indent=2), "index.html": render_html(final)}
    campaign = out / "campaign"
    campaign.mkdir(exist_ok=True)
    files.update({"campaign/world.json": json.dumps(world, ensure_ascii=False, indent=2),
                  "campaign/knowledge.json": json.dumps(final["knowledgeGraph"], ensure_ascii=False, indent=2),
                  "campaign/campaign.json": json.dumps({"format": "mindcrafted-campaign", "version": 2, "world": "world.json", "knowledge": "knowledge.json", "quests": "quests.json", "dialogues": "dialogues.json"}, ensure_ascii=False, indent=2),
                  "campaign/quests.json": json.dumps(world["quests"], ensure_ascii=False, indent=2),
                  "campaign/dialogues.json": json.dumps(world["dialogues"], ensure_ascii=False, indent=2),
                  "campaign/quality.json": json.dumps(report, ensure_ascii=False, indent=2)})
    for kind in ("puzzles", "regions"):
        (campaign / kind).mkdir(exist_ok=True)
        for item in world[kind]:
            files[f"campaign/{kind}/{item['id']}.json"] = json.dumps(item, ensure_ascii=False, indent=2)
    # Replace each file atomically. Rejected candidates never enter the published path.
    for filename, data in files.items():
        target = out / filename
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False, prefix=".world-") as tmp:
            tmp.write(data)
            temporary = Path(tmp.name)
        temporary.replace(target)
    return str(out / "index.html")
