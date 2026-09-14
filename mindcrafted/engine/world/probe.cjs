/* Execute a solver-produced walkthrough against the real engine. */
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {WorldEngine} = require('./core.js');

const {world, walkthrough} = JSON.parse(fs.readFileSync(0, 'utf8'));
const engine = new WorldEngine(world);
const observations = [], solved = [];
engine.events.on('learning.observation', e => observations.push(e));
engine.events.on('puzzle.solved', e => solved.push(e.puzzleId));
for (const [i, action] of walkthrough.entries()) {
  try {
    if (action.type === 'move') assert.equal(engine.move(action.direction), true, 'Movement blocked');
    else if (action.type === 'interact') assert.equal(engine.interact(action.entityId), true, 'Interaction rejected');
    else if (action.type === 'dialogue') { assert.ok(engine.state.dialogue); engine.advanceDialogue(); }
    else throw new Error('Unknown action');
  } catch (error) { throw new Error(`Step ${i} ${JSON.stringify(action)} at ${JSON.stringify(engine.state.player)}: ${error.message}`); }
}
assert.equal(engine.state.completed, true);
assert.equal(new Set(solved).size, world.puzzles.length);
assert.equal(observations.length, world.puzzles.reduce((sum, p) => sum + p.knowledge.requiredRules.length, 0));
assert.ok(observations.every(e => e.correct));
const restored = new WorldEngine(world);
assert.equal(restored.restore(engine.snapshot()), true);
assert.equal(restored.state.completed, true);
assert.equal(restored.state.xp, engine.state.xp);
assert.deepEqual(restored.state.inventory, engine.state.inventory);
process.stdout.write(JSON.stringify({ok: true, steps: walkthrough.length, observations: observations.length}));
