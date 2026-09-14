"""Wrong submissions must reset all stable archetypes without losing solvability."""
import json
from pathlib import Path
import subprocess

import pytest

from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint


@pytest.mark.parametrize("kind", ["switch_sequence", "route_network", "push_blocks"])
def test_failure_reset_and_solution_in_real_runtime(kind):
    world = compile_world(demo_blueprint((kind,)), SOURCE)
    report = validate_world(world, SOURCE)
    script = r"""
const assert = require('node:assert/strict');
const {WorldEngine} = require('./mindcrafted/engine/world/core.js');
const {world, report} = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const e = new WorldEngine(world), p = world.puzzles[0], s = e.state.puzzles[p.id];
const started = [], observed = [], movement = [];
e.events.on('puzzle.started', ev => started.push(ev));
e.events.on('learning.observation', ev => observed.push(ev));
e.events.on('player.moved', ev => movement.push(ev));
e.move('right'); e.interact(p.id + '_mentor'); e.advanceDialogue();
assert.equal(started.length, 1);
if (p.archetype === 'switch_sequence') {
  for (const a of [...report.solutions[p.id].actions].reverse()) {
    const control = [...e.entities.values()].find(n => n.controlId === a.controlId);
    e.state.player = {x:control.x-1, y:control.y, direction:'right'};
    assert.ok(e.interact(control.id));
  }
} else if (p.archetype === 'route_network') {
  s.routes = {A:'B', E:'B', F:'B', G:'B', B:'D', C:'D'};
  const console = e.entities.get(p.world.anchorEntity);
  e.state.player = {x:console.x-1,y:console.y,direction:'right'};
  e.interact(console.id);
} else {
  const goals = p.mechanics.goals;
  s.blocks = [goals[1], goals[2], {...goals[0], x:goals[0].x-1}].map(b => ({x:b.x,y:b.y}));
  e.state.player = {x:p.world.offset.x+goals[0].x-2, y:p.world.offset.y+goals[0].y, direction:'right'};
  assert.ok(e.move('right'));
  assert.deepEqual(movement.at(-1), e.state.player, 'Movement event must reflect the automatic recovery position');
}
assert.equal(s.solved, false); assert.equal(s.errors, 1); assert.equal(s.attempts, 1);
assert.equal(e.isOpen(e.entities.get(p.success.openEntity)), false);
assert.equal(e.state.xp, 0); assert.deepEqual(e.state.inventory, []);
assert.ok(observed.some(ev => !ev.correct));
assert.deepEqual(s.sequence, []); assert.deepEqual(s.routes, {});
assert.deepEqual(s.blocks, (p.mechanics.blocks || []).map(b => ({x:b.x,y:b.y})));
assert.ok(e.reset());
e.state.player = {x:world.player.x,y:world.player.y,direction:'down'};
for (const a of report.walkthrough) {
  if (a.type === 'move') assert.ok(e.move(a.direction));
  else if (a.type === 'interact') assert.ok(e.interact(a.entityId));
  else e.advanceDialogue();
}
assert.equal(e.state.completed, true); assert.equal(s.attempts, 2);
assert.equal(started.length, 1, 'Revisiting the mentor must not start a second learning attempt');
assert.equal(e.state.xp, p.success.xp);
assert.equal(observed.length, p.knowledge.requiredRules.length * 2);
const restored = new WorldEngine(world); restored.restore(e.snapshot());
assert.equal(restored.state.completed, true);
assert.equal(restored.state.puzzles[p.id].invalidActions, s.invalidActions);
assert.equal(restored.state.puzzles[p.id].solutionSteps, s.solutionSteps);
"""
    result = subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1],
                            input=json.dumps({"world": world, "report": report}), text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
