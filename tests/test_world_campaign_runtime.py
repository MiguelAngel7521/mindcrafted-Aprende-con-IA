"""Campaign composition runs the real engines and solver paths without a browser."""

import json
import hashlib
import subprocess
from pathlib import Path

import pytest

from mindcrafted.generator.world import compile_world, validate_world, world_hash
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def campaign_runtime_data():
    world = compile_world(demo_blueprint(("switch_sequence",)), SOURCE)
    return {
        "campaign": {
            "format": "mindcrafted-campaign",
            "version": 2,
            "id": "fixture_campaign", "title": "Campaña de prueba",
            "regions": [
                {"id": region_id, "worldHash": world_hash(world), "sourceHash": hashlib.sha256(SOURCE.encode()).hexdigest(), "world": world}
                for region_id in ("lesson_1", "lesson_2")
            ],
        },
        "walkthrough": validate_world(world, SOURCE)["walkthrough"],
    }


PRELUDE = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
// The campaign module must also load core.js when required directly from Node.
const {CampaignSession} = require('./mindcrafted/engine/world/campaign.js');
const {EventBus, SaveSystem} = require('./mindcrafted/engine/world/core.js');
const {campaign, walkthrough} = JSON.parse(fs.readFileSync(0, 'utf8'));
const copy = value => JSON.parse(JSON.stringify(value));
function act(engine, action) {
  if (action.type === 'move') assert.equal(engine.move(action.direction), true);
  else if (action.type === 'interact') assert.equal(engine.interact(action.entityId), true);
  else if (action.type === 'dialogue') { assert.ok(engine.state.dialogue); engine.advanceDialogue(); }
  else assert.fail('Unknown action: ' + action.type);
}
function finish(session) { for (const action of walkthrough) act(session.engine, action); }
"""


def run_node(data, script):
    result = subprocess.run(
        ["node", "-e", PRELUDE + script],
        cwd=ROOT,
        input=json.dumps(data),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_campaign_walkthrough_and_shared_events(campaign_runtime_data):
    run_node(campaign_runtime_data, r"""
const events = new EventBus(), session = new CampaignSession(campaign, {events});
const first = session.engine, messages = [], observations = [], changes = [], saves = [];
assert.equal(globalThis.MindCraftedWorld.CampaignSession, CampaignSession);
assert.equal(session.events, events);
assert.equal(session.engine.events, events);
events.on('world.message', event => messages.push(event));
events.on('learning.observation', event => observations.push([session.index, event]));
events.on('campaign.region.changed', event => changes.push(event));
events.on('world.changed', () => saves.push(session.snapshot()));
assert.equal(session.advance(), false);
assert.equal(session.index, 0);
const gate = [...first.entities.values()].find(entity => entity.type === 'door');
assert.equal(first.tileFree(gate.x, gate.y), false);
finish(session);
assert.equal(first.state.completed, true);
assert.equal(session.index, 0, 'Engine completion must not advance while its events are being dispatched');
assert.equal(session.completed, false, 'Completing a lesson must not finish a campaign');
assert.equal(session.advance(), true);
assert.equal(session.index, 1);
assert.notEqual(session.engine, first);
assert.equal(session.engine.events, events);
assert.deepEqual(changes, [{index: 1, regionId: 'lesson_2'}]);
assert.equal(saves.at(-1).currentRegion, 1, 'Transitions must trigger persistence');
const puzzleId = first.spec.puzzles[0].id;
assert.equal(session.engine.state.puzzles[puzzleId].solved, false, 'Repeated lesson puzzle IDs stay independent');
assert.deepEqual(session.engine.state.flags, {});
assert.equal(session.engine.tileFree(gate.x, gate.y), false, 'The second lesson has its own locked gate');
assert.equal(session.xp, first.state.xp);
assert.deepEqual(session.inventory, first.state.inventory);
assert.equal(session.advance(), false);
finish(session);
assert.equal(session.completed, true);
assert.equal(session.advance(), false);
assert.equal(session.xp, 2 * first.state.xp);
assert.equal(session.inventory.length, 2);
assert.deepEqual(session.inventory, [puzzleId + '_energy', puzzleId + '_energy']);
assert.equal(observations.length, 2 * first.spec.puzzles[0].knowledge.requiredRules.length);
assert.ok(observations.some(([index]) => index === 0) && observations.some(([index]) => index === 1));
assert.ok(messages.length > 0);
assert.deepEqual(session.snapshot().regions[0].state, first.snapshot(), 'Previous engine state remains intact');
""")


def test_campaign_save_reload_preserves_progress(campaign_runtime_data):
    run_node(campaign_runtime_data, r"""
const session = new CampaignSession(campaign);
finish(session);
assert.ok(session.advance());
const puzzleId = session.engine.spec.puzzles[0].id;
let pausedAt = 0;
for (const [index, action] of walkthrough.entries()) {
  act(session.engine, action);
  if (session.engine.state.puzzles[puzzleId].sequence.length === 1) { pausedAt = index + 1; break; }
}
assert.ok(pausedAt > 0);
const original = session.snapshot(), values = new Map();
const storage = {getItem: key => values.get(key), setItem: (key, value) => values.set(key, value)};
const saves = new SaveSystem(storage, 'course:campaign', 'campaign-hash');
assert.ok(saves.save(session));
const restored = new CampaignSession(campaign), learning = [], changes = [];
restored.events.on('learning.observation', event => learning.push(event));
restored.events.on('campaign.region.changed', event => changes.push(event));
assert.ok(saves.load(restored));
assert.equal(restored.index, 1);
assert.deepEqual(restored.engine.state.player, original.regions[1].state.player);
assert.deepEqual(restored.engine.state.puzzles[puzzleId], original.regions[1].state.puzzles[puzzleId]);
assert.deepEqual(restored.snapshot().regions[0].state.flags, original.regions[0].state.flags);
assert.equal(restored.xp, session.xp);
assert.deepEqual(restored.inventory, session.inventory);
assert.equal(learning.length, 0, 'Reload must not replay BKT observations');
assert.deepEqual(changes, [{index: 1, regionId: 'lesson_2'}]);
assert.ok(saves.load(restored));
assert.equal(restored.xp, session.xp, 'Repeated loads must not duplicate XP');
assert.deepEqual(restored.inventory, session.inventory);
for (const action of walkthrough.slice(pausedAt)) act(restored.engine, action);
assert.ok(restored.completed);
assert.ok(saves.save(restored));
const completed = new CampaignSession(campaign);
assert.ok(saves.load(completed));
assert.ok(completed.completed);
assert.equal(completed.xp, restored.xp);
assert.deepEqual(completed.inventory, restored.inventory);
assert.equal(new SaveSystem(storage, 'another-course', 'campaign-hash').load(completed), false);
""")


def test_campaign_restore_rejects_skips_and_hash_changes(campaign_runtime_data):
    run_node(campaign_runtime_data, r"""
const finished = new CampaignSession(campaign);
finish(finished); assert.ok(finished.advance()); finish(finished);
const completeSave = finished.snapshot();
const session = new CampaignSession(campaign), original = session.snapshot(), events = [];
session.events.on('world.changed', event => events.push(event));
session.events.on('campaign.region.changed', event => events.push(event));
const mutations = [
  raw => { raw.currentRegion = 1; },
  raw => { raw.regions[0].worldHash = 'changed'; },
  raw => { raw.regions[1].worldHash = 'changed'; },
  raw => { raw.regions.reverse(); },
  raw => { raw.regions.pop(); },
  raw => { raw.version = 1; },
  raw => { raw.currentRegion = 24; },
  raw => { raw.currentRegion = -1; },
  raw => { raw.currentRegion = '1'; },
  raw => { raw.regions[0].state = []; },
  raw => {
    raw.currentRegion = 1;
    raw.regions[0].state.completed = true;
    raw.regions[0].state.puzzles.sequence.solved = true;
    raw.regions[0].state.flags.sequence_restored = true;
  },
];
for (const mutate of mutations) {
  const raw = copy(original); mutate(raw);
  assert.equal(session.restore(raw), false);
  assert.deepEqual(session.snapshot(), original, 'Rejected save must be transactional');
}
assert.equal(events.length, 0, 'Rejected saves must not reach autosave/learning/UI listeners');
const forged = copy(original);
forged.regions[0].state = {...forged.regions[0].state, xp: 999999, inventory: ['forged'], completed: true,
  flags: {sequence_restored: true}, player: completeSave.regions[0].state.player};
forged.regions[0].state.puzzles.sequence.solved = true;
forged.regions[1].state = completeSave.regions[1].state;
assert.ok(session.restore(forged));
assert.equal(session.index, 0);
assert.equal(session.completed, false);
assert.equal(session.engine.state.completed, false);
assert.equal(session.xp, 0);
assert.deepEqual(session.inventory, []);
assert.deepEqual(session.engine.state.flags, {});
assert.deepEqual(session.engine.state.player, original.regions[0].state.player, 'A forged position cannot cross a closed gate');
assert.deepEqual(session.snapshot().regions[1].state, original.regions[1].state, 'Future solutions and rewards must be discarded');
assert.equal(session.advance(), false);
assert.ok(session.restore(completeSave));
const validRewards = session.xp;
completeSave.regions[0].state.xp = 999999;
completeSave.regions[0].state.inventory = ['forged'];
assert.ok(session.restore(completeSave));
assert.equal(session.xp, validRewards, 'Solved regions derive their rewards from the spec');
assert.deepEqual(session.inventory, ['sequence_energy', 'sequence_energy']);
""")


def test_campaign_input_bounds(campaign_runtime_data):
    run_node(campaign_runtime_data, r"""
for (const raw of [null, [], {}, {...campaign, format: 'other'}, {...campaign, version: 1},
                   {...campaign, regions: []}, {...campaign, regions: [campaign.regions[0], campaign.regions[0]]},
                   {...campaign, regions: Array.from({length: 25}, (_, i) => ({...campaign.regions[0], id: 'r' + i}))},
                   {...campaign, regions: [{...campaign.regions[0], id: '../lesson'}]},
                   {...campaign, regions: [{...campaign.regions[0], worldHash: ''}]}]) {
  assert.throws(() => new CampaignSession(raw));
}
const max = new CampaignSession({...campaign, regions: Array.from({length: 24}, (_, i) => ({...campaign.regions[0], id: 'r' + i}))});
assert.equal(max.snapshot().regions.length, 24);
const single = new CampaignSession({...campaign, regions: [campaign.regions[0]]});
finish(single);
assert.ok(single.completed);
assert.equal(single.advance(), false);
for (const raw of [null, [], {}, {version: 2}]) assert.equal(single.restore(raw), false);
""")
