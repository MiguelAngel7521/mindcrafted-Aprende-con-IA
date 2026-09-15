"""Contracts connecting the new graph mechanic to the existing World V2 pipeline."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import random
import subprocess

import pytest

from mindcrafted.generator.node_connect import simulate
from mindcrafted.generator.node_connect_demo import SOURCE, blueprint
from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_knowledge import build_knowledge_graph
from mindcrafted.generator.world_package import make_package, quality_gate, runtime_probe
from mindcrafted.generator.world_pipeline import generate_campaign
from mindcrafted.generator.world_schema import NodeConnect

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def connection_world():
    return compile_world(blueprint(), SOURCE, difficulty="hard")


def node(script, data):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps(data), text=True,
                            capture_output=True, timeout=40)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout or "null")


def test_full_contract_world_graph_solver_runtime_and_knowledge(connection_world):
    world = connection_world
    report = validate_world(world, SOURCE)
    assert report["ok"], report["errors"]
    puzzle = world["puzzles"][0]
    entities = {e["id"]: e for e in world["regions"][0]["entities"]}
    assert puzzle["runtime"] == "world" and puzzle["mandatory"] and puzzle["resettable"]
    assert entities[puzzle["world"]["anchorEntity"]]["type"] == "console"
    assert entities[puzzle["success"]["openEntity"]]["type"] == "door"
    assert sum(e["type"] == "connection_node" for e in entities.values()) == len(puzzle["mechanics"]["nodes"])
    assert runtime_probe(world, report["walkthrough"])["ok"]
    assert report["solutions"][puzzle["id"]]["solutionCount"] > 1
    graph = build_knowledge_graph(world, SOURCE)
    assert {binding["ruleId"] for r in graph["rules"] for binding in r["bindings"]} == {"layering", "single_entry", "availability"}
    assert any(path.startswith("/mechanics/connectionRules/") for r in graph["rules"] for b in r["bindings"] for path in b["mechanicPaths"])
    assert make_package(world, SOURCE)["knowledgeGraph"] == graph


def test_standalone_schema_matches_runtime_contract():
    assert json.loads((ROOT / "mindcrafted/engine/world/node-connect.schema.json").read_text()) == NodeConnect.model_json_schema()


@pytest.mark.parametrize("mutate", [
    lambda w: w["puzzles"][0]["mechanics"].update(javascript="alert(1)"),
    lambda w: w["puzzles"][0]["mechanics"].update(schemaVersion=2),
    lambda w: w["puzzles"][0].update(runtime="iframe"),
    lambda w: w["puzzles"][0]["world"].update(anchorEntity="missing"),
    lambda w: w["puzzles"][0]["success"].update(openEntity="layers_UI"),
    lambda w: w["puzzles"][0]["mechanics"]["connectionRules"][0].update(ruleId="missing"),
    lambda w: w["puzzles"][0]["mechanics"]["goals"][0].update(target="missing"),
    lambda w: w["puzzles"][0]["mechanics"]["nodes"][0].update(id="constructor"),
    lambda w: w["puzzles"][0]["knowledge"]["requiredRules"][0].update(evidence="Una evidencia que no existe en el material del alumno"),
])
def test_invalid_generated_data_is_rejected(connection_world, mutate):
    world = deepcopy(connection_world)
    mutate(world)
    assert not validate_world(world, SOURCE)["ok"]


def test_physical_node_cannot_be_missing_or_inaccessible(connection_world):
    world = deepcopy(connection_world)
    world["regions"][0]["entities"] = [e for e in world["regions"][0]["entities"] if e["id"] != "layers_REPO"]
    assert not validate_world(world, SOURCE)["ok"]
    world = deepcopy(connection_world)
    region = world["regions"][0]
    for y in range(region["height"]):
        row = list(region["tiles"][y]); row[8] = "#"; region["tiles"][y] = "".join(row)
    report = validate_world(world, SOURCE)
    assert not report["ok"] and any("Softlock" in error for error in report["errors"])


def test_browser_simulator_matches_python_for_every_graph_and_rule_ablation(connection_world):
    m = connection_world["puzzles"][0]["mechanics"]
    cases = [[e["id"] for index, e in enumerate(m["edges"]) if mask & (1 << index)] for mask in range(1 << len(m["edges"]))]
    results = node(r"""
const {nodeConnectResult} = require('./mindcrafted/engine/world/node-connect.js');
const {mechanics, cases} = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(cases.map(connections => [null, 'layering', 'single_entry', 'availability'].map(ignored => nodeConnectResult(mechanics, connections, ignored)))));
""", {"mechanics": m, "cases": cases})
    for connections, row in zip(cases, results):
        for ignored, actual in zip([None, "layering", "single_entry", "availability"], row):
            assert actual == simulate(m, connections, ignored_rule=ignored), (connections, ignored)


def test_partial_save_selection_disconnect_failure_and_idempotent_rewards(connection_world):
    node(r"""
const assert = require('node:assert/strict');
const {WorldEngine, SaveSystem} = require('./mindcrafted/engine/world/core.js');
const world = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let e = new WorldEngine(world);
assert.equal(e.interact('layers_UI'), false, 'Remote graph editing forbidden');
e.move('right'); e.interact(); e.advanceDialogue();
function touch(id) { const entity = e.entities.get(id); e.state.player = {x:entity.x-1,y:entity.y}; assert.ok(e.interact(id)); }
touch('layers_UI');
const store = new Map(), storage = {getItem:key=>store.get(key),setItem:(key,value)=>store.set(key,value)};
const saves = new SaveSystem(storage, 'course:connect', 'samehash'); saves.save(e);
e = new WorldEngine(world); assert.ok(saves.load(e));
assert.equal(e.state.puzzles.layers.selectedNode, 'UI');
touch('layers_API');
assert.deepEqual(e.state.puzzles.layers.connections, ['UI_API']);
touch('layers_UI'); touch('layers_API');
assert.deepEqual(e.state.puzzles.layers.connections, [], 'Selecting the pair again disconnects');
touch('layers_UI'); touch('layers_UI');
assert.equal(e.state.puzzles.layers.selectedNode, null, 'Repeated source cancels');
touch('layers_UI'); touch('layers_DB'); touch('layers_console');
const s = e.state.puzzles.layers;
assert.equal(s.solved, false); assert.equal(s.attempts, 1); assert.equal(s.errors, 1);
assert.deepEqual(s.connections, []); assert.deepEqual(s.effect.invalidEdges, ['UI_DB']);
assert.equal(e.isOpen(e.entities.get('layers_gate')), false);
e.hint(); assert.equal(s.hintsUsed, 1); assert.equal(e.reset(), true);
assert.equal(s.effect, null);
touch('layers_UI'); touch('layers_ALT');
saves.save(e); e = new WorldEngine(world); assert.ok(saves.load(e));
assert.deepEqual(e.state.puzzles.layers.connections, ['UI_ALT']);
const observations = []; e.events.on('learning.observation', event => observations.push(event));
touch('layers_ALT'); touch('layers_REPO'); touch('layers_REPO'); touch('layers_DB'); touch('layers_console');
assert.equal(e.state.puzzles.layers.solved, true);
assert.equal(e.state.quests.layers_quest, 'complete');
assert.equal(e.isOpen(e.entities.get('layers_gate')), true);
e.advanceDialogue(); touch('layers_mentor'); assert.equal(e.state.dialogue.id, 'layers_after'); e.advanceDialogue();
assert.equal(e.state.flags.layers_understood, true);
assert.equal(observations.length, 3);
saves.save(e); assert.ok(saves.load(e)); assert.ok(saves.load(e));
assert.equal(e.state.xp, 75); assert.equal(e.state.inventory.length, 1);
assert.equal(observations.length, 3);
assert.equal(e.reset('layers'), false);
const forged = e.snapshot(); forged.puzzles.layers.connections = ['UI_DB', 'missing', 'UI_DB'];
forged.puzzles.layers.selectedNode = 'missing'; forged.puzzles.layers.effect = {ok:true, connections:['missing']};
e.restore(forged);
assert.equal(e.state.puzzles.layers.solved, false);
assert.equal(e.state.flags.layers_restored, undefined);
assert.equal(e.state.xp, 0);
assert.equal(e.state.puzzles.layers.selectedNode, null);
""", connection_world)


def test_random_toggle_decisions_recover_and_do_not_easily_solve(connection_world):
    m = connection_world["puzzles"][0]["mechanics"]
    rng = random.Random(271828)
    trials = []
    for _ in range(256):
        toggles = [rng.choice(m["edges"])["id"] for _ in range(rng.randint(1, 24))]
        selected = set()
        for edge in toggles:
            selected.symmetric_difference_update([edge])
        trials.append({"toggles": toggles, "ok": simulate(m, sorted(selected))["ok"]})
    assert sum(case["ok"] for case in trials) / len(trials) < .1
    node(r"""
const assert = require('node:assert/strict');
const {WorldEngine} = require('./mindcrafted/engine/world/core.js');
const {world, trials} = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for (const trial of trials) {
  const e = new WorldEngine(world); e.move('right'); e.interact(); e.advanceDialogue();
  function touch(control) { const entity = [...e.entities.values()].find(n=>n.controlId === control); e.state.player={x:entity.x-1,y:entity.y}; e.interact(entity.id); }
  for (const id of trial.toggles) { const edge = world.puzzles[0].mechanics.edges.find(e=>e.id===id); touch(edge.source); touch(edge.target); }
  e.state.player={x:6,y:9}; e.interact('layers_console');
  assert.equal(e.state.puzzles.layers.solved, trial.ok);
  if (!trial.ok) {
    assert.ok(e.reset());
    for (const [source,target] of [['UI','API'],['API','REPO'],['REPO','DB']]) { touch(source); touch(target); }
    e.state.player={x:6,y:9}; e.interact('layers_console');
  }
  assert.equal(e.state.puzzles.layers.solved, true);
  const reloaded = new WorldEngine(world); reloaded.restore(e.snapshot());
  assert.equal(reloaded.state.xp, 75); assert.equal(reloaded.state.puzzles.layers.solved, true);
}
""", {"world": connection_world, "trials": trials})


def test_ai_generation_repairs_node_connect_and_publishes_after_real_gate(tmp_path):
    calls = []

    async def model(prompt, system, **kwargs):
        calls.append(kwargs["step"])
        request = json.loads(prompt)
        if kwargs["step"] == "world_blueprint":
            assert "node_connect" in json.dumps(request["schema"]) and "node_connect" in system
            design = blueprint()
            if len(calls) == 1:
                design["puzzles"][0]["mechanics"]["edges"][0]["target"] = "missing"
            else:
                assert request["repair"]["errors"]
            return json.dumps(design)
        assert all(request["tests"].values())
        assert request["world"]["puzzles"][0]["archetype"] == "node_connect"
        return json.dumps({"approved": True, "scores": {key: 24 for key in (
            "embodiedLearning", "worldIntegration", "interactionQuality", "technicalSolvability")}, "issues": []})

    path = asyncio.run(generate_campaign(SOURCE, tmp_path, generate=model, parse_json=lambda raw, label: json.loads(raw), difficulty="hard"))
    package = json.loads((tmp_path / "game.pkg.json").read_text())
    assert calls == ["world_blueprint", "world_blueprint", "world_judge"]
    assert path.endswith("index.html") and package["quality"]["approved"]
    assert package["quality"]["e2e"]["recovery"]
    assert (tmp_path / "campaign/puzzles/layers.json").exists()
    assert not any(token in package for token in ("javascript", "minigames_js"))


def test_perfect_judge_cannot_override_unsolvable_connection_graph(connection_world):
    world = deepcopy(connection_world)
    world["puzzles"][0]["mechanics"]["goals"].append({"source": "DB", "target": "UI", "ruleId": "availability"})
    judge = {"approved": True, "scores": {key: 25 for key in (
        "embodiedLearning", "worldIntegration", "interactionQuality", "technicalSolvability")}, "issues": []}
    report = quality_gate(world, SOURCE, judge=judge)
    assert report["checks"]["schema"] and not report["checks"]["solver"]
    assert not report["approved"] and report["errors"]


def test_mixed_world_and_repeated_graph_ids_in_campaign_reload(tmp_path):
    from mindcrafted.generator.world_campaign import assemble_campaign, write_campaign
    from mindcrafted.generator.world_demo import SOURCE as routing_source, demo_blueprint

    combined_source = routing_source + "\n" + SOURCE
    mixed = demo_blueprint(("route_network",))
    mixed["puzzles"].extend(blueprint()["puzzles"])
    designs = [mixed, blueprint()]
    packages = []
    for index, design in enumerate(designs):
        world = compile_world(design, combined_source, difficulty="hard")
        package = make_package(world, combined_source, f"region_{index}")
        package["developmentDemo"] = True
        packages.append(package)
    package = assemble_campaign(packages, "mixed_connections", development=True)
    manifest = write_campaign(package, tmp_path)
    assert manifest["checks"]["ok"] and manifest["checks"]["recovery"]
    assert manifest["checks"]["reload"] and manifest["checks"]["regions"] == 2
