"""Real engine: checkpoints, phase events, BKT context and derived save state."""
from copy import deepcopy
import json

import pytest

from mindcrafted.generator.world_boss import compile_boss,effective_puzzle,phase_outputs,_states
from mindcrafted.generator.boss_demo import THREE_PHASE_SOURCE as SOURCE,three_phase_blueprint
from mindcrafted.generator.world import validate_world
from test_node_connect_integration import node


@pytest.fixture(scope='module')
def encounter():
    b=three_phase_blueprint()
    world=compile_boss(b,SOURCE,prior_skills=b['requiredSkills'])
    return world,validate_world(world,SOURCE)


def test_three_phase_failure_recovery_partial_reload_bkt_and_completion(encounter):
    world,report=encounter
    node(r"""
const assert=require('node:assert/strict'),{WorldEngine}=require('./mindcrafted/engine/world/core.js');
const {createTracker}=require('./mindcrafted/engine/bkt.js');
const {world,trace}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const e=new WorldEngine(world),store=new Map(),storage={getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)};
const bkt=createTracker({storage,scope:'boss'}),events=[];
for(const name of ['boss.started','boss.phase.started','boss.phase.completed','boss.phase.failed','boss.recovered','boss.completed'])e.events.on(name,p=>events.push({name,...p}));
e.events.on('learning.observation',o=>{assert.ok(o.boss);bkt.observe(o.skill,o.correct,{observations:o.observations,context:o.boss});});
function touch(id){const a=e.entities.get(id);const pos=[[a.x-1,a.y],[a.x+1,a.y],[a.x,a.y-1],[a.x,a.y+1]].find(([x,y])=>e.tileFree(x,y));e.state.player={x:pos[0],y:pos[1],direction:'right'};assert.ok(e.interact(id));}
let injected=false;
for(const action of trace){
 if(action.type==='move')assert.ok(e.move(action.direction));
 else if(action.type==='interact')assert.ok(e.interact(action.entityId));
 else {assert.ok(e.state.dialogue);e.advanceDialogue();}
 if(e.active('machine')&&!e.state.dialogue&&!injected){
  injected=true;
  const origin={...e.state.player},prior=JSON.stringify(e.state.puzzles.layers),shared=JSON.stringify(e.state.bosses.archive_recovery.shared);
  assert.equal(e.bossSystem.allowed('balance'),false);
  assert.notEqual(e.hintText(e.puzzles.get('balance'),4),e.puzzles.get('balance').hint);
  touch('machine_storage');touch('machine_console');
  assert.equal(e.state.puzzles.machine.errors,1);assert.equal(e.state.puzzles.machine.solved,false);
  e.hint();assert.equal(e.state.puzzles.machine.hintsUsed,1);
  assert.ok(e.reset('machine'));
  assert.equal(JSON.stringify(e.state.puzzles.layers),prior);
  assert.equal(JSON.stringify(e.state.bosses.archive_recovery.shared),shared);
  touch('machine_storage');const partial=e.snapshot(),mastery=bkt.summary(),eventCount=events.length;
  partial.bosses.archive_recovery.shared.memory_budget=100;
  partial.bosses.archive_recovery.phaseIndex=3;partial.bosses.archive_recovery.status='complete';
  assert.ok(e.restore(partial));assert.equal(e.state.puzzles.machine.configuration.storage,'volatile');
  assert.equal(JSON.stringify(e.state.bosses.archive_recovery.shared),shared);
  assert.equal(e.state.bosses.archive_recovery.phaseIndex,1);
  assert.deepEqual(bkt.summary(),mastery);assert.equal(events.length,eventCount);
  assert.ok(e.reset('machine'));e.state.player=origin;
 }
}
assert.ok(injected);assert.equal(e.state.completed,true);assert.equal(e.state.xp,350);
assert.equal(e.state.bosses.archive_recovery.status,'complete');assert.equal(e.state.flags.archive_recovered,true);
assert.equal(events.filter(v=>v.name==='boss.started').length,1);
assert.equal(events.filter(v=>v.name==='boss.phase.started').length,3);
assert.equal(events.filter(v=>v.name==='boss.phase.completed').length,3);
assert.equal(events.filter(v=>v.name==='boss.phase.failed').length,1);
assert.equal(events.filter(v=>v.name==='boss.recovered').length,2);
assert.equal(events.filter(v=>v.name==='boss.completed').length,1);
assert.equal(bkt.summary().records.length,13);
for(const r of bkt.summary().records){
 assert.equal(r.phaseEvidence.length,1);assert.equal(r.phaseEvidence[0].bossId,'archive_recovery');
 assert.equal(r.phaseEvidence[0].attempts,r.skillId.startsWith('configuration.')?2:1);
 if(r.skillId.startsWith('configuration.'))assert.equal(r.phaseEvidence[0].observations.restarts,2);
}
const final=e.snapshot(),observed=bkt.summary(),count=events.length;
assert.ok(e.restore(final));assert.ok(e.restore(final));assert.deepEqual(e.snapshot(),final);
assert.deepEqual(bkt.summary(),observed);assert.equal(events.length,count);
assert.equal(e.reset('machine'),false);
const corrupt=JSON.parse(JSON.stringify(final));corrupt.puzzles.layers.connections=[];
e.restore(corrupt);assert.equal(e.state.bosses.archive_recovery.phaseIndex,0);
assert.deepEqual(e.state.bosses.archive_recovery.shared,{});assert.equal(e.state.xp,0);
assert.equal(e.state.puzzles.machine.solved,false);assert.equal(e.state.puzzles.balance.solved,false);
assert.equal(e.state.flags.archive_recovered,undefined);assert.equal(events.length,count);
""",{'world':world,'trace':report['walkthrough']})


def test_checkpoint_policy_resets_only_current_phase_and_persists_last_failure():
    b=three_phase_blueprint();b['failurePolicy']='checkpoint'
    world=compile_boss(b,SOURCE,prior_skills=b['requiredSkills'])
    report=validate_world(world,SOURCE)
    node(r"""
const assert=require('node:assert/strict'),{WorldEngine,machineConfiguration}=require('./mindcrafted/engine/world/core.js');
const {world,trace}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));const e=new WorldEngine(world);
for(const a of trace){if(a.type==='move')e.move(a.direction);else if(a.type==='interact')e.interact(a.entityId);else e.advanceDialogue();if(e.active('machine')&&!e.state.dialogue)break;}
const p=e.puzzles.get('machine'),prior=JSON.stringify(e.state.puzzles.layers),shared=JSON.stringify(e.state.bosses.archive_recovery.shared);
const anchor=e.entities.get(p.world.anchorEntity);e.state.player={x:anchor.x-1,y:anchor.y,direction:'right'};
e.state.puzzles.machine.configuration.storage='durable';assert.ok(e.interact(anchor.id));
assert.deepEqual(e.state.puzzles.machine.configuration,machineConfiguration.initial(p.mechanics));
assert.equal(e.state.puzzles.machine.errors,1);assert.equal(JSON.stringify(e.state.puzzles.layers),prior);
assert.equal(JSON.stringify(e.state.bosses.archive_recovery.shared),shared);
const failed=e.snapshot();assert.ok(e.restore(failed));assert.deepEqual(e.state.puzzles.machine.effect,failed.puzzles.machine.effect);
assert.equal(e.state.bosses.archive_recovery.phaseIndex,1);assert.ok(e.reset('machine'));
""",{'world':world,'trace':report['walkthrough']})


def test_composition_helpers_match_python_for_all_reachable_variants(encounter):
    from mindcrafted.generator.world_boss import MODULES
    world,report=encounter;boss=world['bosses'][0];puzzles={p['id']:p for p in world['puzzles']}
    cases=[]
    for proof in report['boss']['archive_recovery']['variantProofs']:
        phase=next(p for p in boss['phases'] if p['id']==proof['phaseId'])
        puzzle=puzzles[phase['puzzleId']];effective=effective_puzzle(puzzle,phase,proof['shared'])
        module=MODULES[puzzle['archetype']]
        for state in _states(effective):
            if module.simulate(effective['mechanics'],state)['ok']:
                cases.append({'mechanics':puzzle['mechanics'],'phase':phase,'shared':proof['shared'],
                              'effective':effective['mechanics'],'state':{'connections':state} if isinstance(state,list) else {'configuration':state},
                              'outputs':phase_outputs(phase,state,proof['shared'])})
    node(r"""
const assert=require('node:assert/strict'),{applyBossBindings,bossOutputs}=require('./mindcrafted/engine/world/boss-system.js');
for(const c of JSON.parse(require('node:fs').readFileSync(0,'utf8'))){assert.deepEqual(applyBossBindings(c.mechanics,c.phase,c.shared),c.effective);assert.deepEqual(bossOutputs(c.phase,c.state,c.shared),c.outputs);}
""",cases)


def test_seeded_actions_and_reloads_always_allow_phase_recovery(encounter):
    world,report=encounter
    node(r"""
const assert=require('node:assert/strict'),{WorldEngine,machineConfiguration}=require('./mindcrafted/engine/world/core.js');
const {world,trace}=JSON.parse(require('node:fs').readFileSync(0,'utf8')),e=new WorldEngine(world);
for(const a of trace){if(a.type==='move')e.move(a.direction);else if(a.type==='interact')e.interact(a.entityId);else e.advanceDialogue();if(e.active('machine')&&!e.state.dialogue)break;}
const checkpoint=e.snapshot(),m=e.puzzles.get('machine').mechanics,controls=[...m.slots,...m.parameters].map(c=>c.id);
let seed=20260915;const random=n=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%n;};
function touch(id){const a=e.entities.get(id),pos=[[a.x-1,a.y],[a.x+1,a.y],[a.x,a.y-1],[a.x,a.y+1]].find(([x,y])=>e.tileFree(x,y));e.state.player={x:pos[0],y:pos[1],direction:'right'};return e.interact(id);}
for(let trial=0;trial<128;trial++){
 e.restore(checkpoint);
 for(let step=0;step<12;step++){
  if(e.state.puzzles.machine.solved)break;
  const action=random(8);
  if(action<5)touch('machine_'+controls[action]);else if(action===5)touch('machine_console');else if(action===6)e.hint();else e.restore(e.snapshot());
  assert.deepEqual(e.state.puzzles.layers,checkpoint.puzzles.layers);
  assert.equal(e.state.bosses.archive_recovery.shared.memory_budget,checkpoint.bosses.archive_recovery.shared.memory_budget);
 }
 if(!e.state.puzzles.machine.solved){assert.ok(e.reset('machine'));assert.deepEqual(e.state.puzzles.machine.configuration,machineConfiguration.initial(m));}
}
""",{'world':world,'trace':report['walkthrough']})
