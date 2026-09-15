"""System extraction must preserve authority, isolation and recovery contracts."""
import json
from pathlib import Path
import random
import subprocess

import pytest

from mindcrafted.generator.world import compile_world
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint
from mindcrafted.generator.world_package import quality_gate
from mindcrafted.generator.world_solver import network_result, route_options

ROOT = Path(__file__).resolve().parents[1]


def run_node(script, data):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps(data),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_system_events_stay_local_and_remain_attached_after_restore():
    world = compile_world(demo_blueprint(), SOURCE)
    run_node(r"""
const assert = require('node:assert/strict');
const {WorldEngine, EventBus} = require('./mindcrafted/engine/world/core.js');
const world = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const bus = new EventBus(), a = new WorldEngine(world, {events: bus}), b = new WorldEngine(world, {events: bus});
const baseline = b.snapshot(), starts = [], completions = [], flags = [];
bus.on('quest.started', event => starts.push(event));
bus.on('quest.completed', event => completions.push(event));
bus.on('world.flag.set', event => flags.push(event));
a.move('right'); a.interact(); a.advanceDialogue();
assert.equal(a.active('routing'), true);
assert.deepEqual(b.snapshot(), baseline, 'Shared campaign observers must not activate another region');
a.interact(); a.advanceDialogue();
assert.equal(starts.length, 1, 'Revisiting the NPC must be idempotent');
const saved = a.snapshot();
a.restore(saved);
// Observer events are not commands: an external event cannot grant critical state.
bus.emit('puzzle.solved', {puzzleId:'routing'});
bus.emit('dialogue.effect', {type:'setFlag', target:'routing_restored'});
assert.equal(a.flagSystem.has('routing_restored'), false);
assert.equal(b.flagSystem.has('routing_restored'), false);
a.state.puzzles.routing.routes = {A:'B', E:'B', F:'C', G:'C', B:'D', C:'D'};
a.state.player = {x:6, y:9}; a.interact('routing_console');
assert.equal(a.state.quests.routing_quest, 'complete');
assert.equal(a.state.dialogue.id, 'routing_after');
a.advanceDialogue();
assert.equal(a.flagSystem.has('routing_understood'), true);
assert.equal(completions.length, 1);
assert.equal(flags.length, 2);
assert.deepEqual(b.snapshot(), baseline);
a.restore(a.snapshot());
assert.equal(completions.length, 1, 'Restore must not replay completion events');
assert.equal(flags.length, 2, 'Restore must not replay flag effects');
assert.equal(a.state.xp, 75);
""", world)


def test_network_feedback_is_recomputed_and_cannot_forge_progress():
    world = compile_world(demo_blueprint(), SOURCE)
    run_node(r"""
const assert = require('node:assert/strict');
const {WorldEngine} = require('./mindcrafted/engine/world/core.js');
const world = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const e = new WorldEngine(world);
e.move('right'); e.interact(); e.advanceDialogue();
e.state.player = {x:6,y:9};
e.state.puzzles.routing.routes = {A:'B',E:'B',F:'B',G:'B',B:'D',C:'D'};
e.interact('routing_console');
const saved = e.snapshot();
saved.puzzles.routing.solved = true;
saved.flags.routing_restored = true;
Object.assign(saved.puzzles.routing.effect, {ok:true, loads:{B:0}, congested:[], successfulRoutes:4});
const restored = new WorldEngine(world); restored.restore(saved);
const state = restored.state.puzzles.routing;
assert.equal(state.solved, false);
assert.equal(state.effect.ok, false);
assert.deepEqual(state.effect.congested, ['B']);
assert.equal(state.effect.loads.B, 4);
assert.equal(state.effect.successfulRoutes, 0);
assert.equal(restored.flagSystem.has('routing_restored'), false);
assert.equal(restored.state.xp, 0);
assert.equal(restored.reset(), true);
assert.equal(state.effect, null);
""", world)


@pytest.mark.parametrize('kind', ['route_network', 'switch_sequence', 'push_blocks'])
def test_hints_progress_from_concept_to_explicit_help(kind):
    world = compile_world(demo_blueprint((kind,)), SOURCE)
    run_node(r"""
const assert = require('node:assert/strict');
const {WorldEngine} = require('./mindcrafted/engine/world/core.js');
const world = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const engine = new WorldEngine(world), puzzle = world.puzzles[0];
const hints = [0,1,2,3,4].map(level => engine.hintText(puzzle, level));
assert.equal(hints[0], '');
assert.equal(new Set(hints).size, 5);
assert.equal(hints[4], world.puzzles[0].hint);
assert.ok(hints.slice(0,4).every(hint => hint !== world.puzzles[0].hint));
""", world)


def test_seeded_random_routing_matches_solver_and_recovers():
    world = compile_world(demo_blueprint(), SOURCE, difficulty="hard")
    mechanics = world["puzzles"][0]["mechanics"]
    options = route_options(mechanics)
    rng = random.Random(20260913)
    trials = []
    for _ in range(256):
        routes = {node: rng.choice(targets) for node, targets in options.items()}
        trials.append({"routes": routes, "ok": network_result(mechanics, routes)["ok"]})
    assert sum(trial["ok"] for trial in trials) / len(trials) <= .1
    run_node(r"""
const assert = require('node:assert/strict');
const {WorldEngine} = require('./mindcrafted/engine/world/core.js');
const {world, trials} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
for (const trial of trials) {
  const e = new WorldEngine(world); e.move('right'); e.interact(); e.advanceDialogue();
  const s = e.state.puzzles.routing;
  // Unit setup isolates randomized arbitration; the browser test walks to every control.
  e.state.player = {x:6,y:9}; s.routes = {...trial.routes}; e.interact('routing_console');
  assert.equal(s.solved, trial.ok, JSON.stringify(trial));
  if (!trial.ok) {
    assert.equal(e.reset(), true);
    assert.deepEqual(s.routes, {});
    assert.equal(e.state.xp, 0);
    s.routes = {A:'B',E:'B',F:'C',G:'C',B:'D',C:'D'};
    e.interact('routing_console'); assert.equal(s.solved, true);
  }
  const restored = new WorldEngine(world); restored.restore(e.snapshot());
  assert.equal(restored.state.xp, 75);
  assert.equal(restored.state.puzzles.routing.effect.ok, true);
  assert.equal(restored.isOpen(restored.entities.get('routing_gate')), true);
}
""", {"world": world, "trials": trials})


def test_perfect_judge_cannot_override_unsolvable_routing():
    world = compile_world(demo_blueprint(), SOURCE)
    for node in world["puzzles"][0]["mechanics"]["nodes"]:
        if node["id"] in ("B", "C"):
            node["capacity"] = 1
    judge = {"approved": True, "scores": {key: 25 for key in (
        "embodiedLearning", "worldIntegration", "interactionQuality", "technicalSolvability")}, "issues": []}
    report = quality_gate(world, SOURCE, judge=judge)
    assert report["checks"]["schema"] is True
    assert report["checks"]["solver"] is False
    assert report["approved"] is False
    assert any("congestión" in error for error in report["errors"])
