"""Independent random action sequences, all-state recovery and save validation."""
from itertools import product
import random

from mindcrafted.generator import machine_configuration as mechanic
from mindcrafted.generator.machine_configuration_demo import SOURCE, blueprint
from mindcrafted.generator.world import compile_world
from test_node_connect_integration import node


def test_seeded_machine_actions_match_simulator_and_do_not_win_frequently():
    p = blueprint()['puzzles'][0]; m = p['mechanics']
    rng = random.Random(1618033)
    trials = []
    for _ in range(256):
        state = mechanic.initial(m); actions = []
        for _ in range(rng.randint(1, 40)):
            action = {'type':'reset'} if rng.randrange(16) == 0 else {'type':'control','controlId':rng.choice(list(state))}
            actions.append(action); state = mechanic.transition(m, state, action)
        trials.append({'actions':actions,'state':state,'result':mechanic.simulate(m,state)})
    assert sum(t['result']['ok'] for t in trials) / len(trials) < .1
    node("""
const assert=require('node:assert/strict'),{machineConfiguration:m}=require('./mindcrafted/engine/world/machine-configuration.js');
const d=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for(const t of d.trials){
 let state=m.initial(d.m);
 for(const action of t.actions){const old=JSON.stringify(state);const next=m.transition(d.m,state,action);assert.equal(JSON.stringify(state),old);state=next;}
 assert.deepEqual(state,t.state);assert.deepEqual(m.result(d.m,state),t.result);
 assert.deepEqual(m.transition(d.m,state,{type:'reset'}),m.initial(d.m));
}
""", {'m':m,'trials':trials})


def test_every_machine_configuration_recovers_with_real_controls_and_restores():
    world = compile_world(blueprint(), SOURCE, difficulty='hard')
    p = world['puzzles'][0]; domains = mechanic.domains(p['mechanics'])
    cases = [dict(zip(domains, values)) for values in product(*domains.values())]
    node("""
const assert=require('node:assert/strict'),{WorldEngine,SaveSystem,machineConfiguration:m}=require('./mindcrafted/engine/world/core.js');
const {world,cases,solution}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const p=world.puzzles[0],domains=m.domains(p.mechanics),copy=v=>JSON.parse(JSON.stringify(v));
for(const configuration of cases){
 let e=new WorldEngine(world),observations=[];
 function listen(){e.events.on('learning.observation',o=>observations.push(o));}
 listen();
 function touch(control){const n=e.entities.get('machine_'+control);e.state.player={x:n.x-1,y:n.y};assert.equal(e.interact(n.id),true);}
 function configure(target){for(const [id,value] of Object.entries(target)){
  const choices=domains[id],current=e.state.puzzles.machine.configuration[id];
  for(let i=(choices.indexOf(value)-choices.indexOf(current)+choices.length)%choices.length;i>0;i--)touch(id);
 }}
 assert.equal(e.interact('machine_storage'),false);
 touch('mentor');e.advanceDialogue();configure(configuration);
 const storageMap=new Map(),storage={getItem:k=>storageMap.get(k),setItem:(k,v)=>storageMap.set(k,v)};
 const saves=new SaveSystem(storage,'course:machine','same-hash');
 saves.save(e);e=new WorldEngine(world);listen();assert.ok(saves.load(e));
 assert.deepEqual(e.state.puzzles.machine.configuration,configuration);assert.equal(observations.length,0);
 const result=m.result(p.mechanics,configuration);
 touch('console');assert.equal(e.state.puzzles.machine.solved,result.ok);
 assert.deepEqual(e.state.puzzles.machine.effect,result);
 assert.equal(observations.length,7);assert.deepEqual(observations.map(o=>o.correct),p.knowledge.requiredRules.map(r=>result.rules[r.id]));
 if(!result.ok){
  const failure=e.snapshot();saves.save(e);assert.ok(saves.load(e));
  assert.deepEqual(e.state.puzzles.machine.effect,failure.puzzles.machine.effect);
  assert.equal(e.state.xp,0);assert.equal(e.state.flags.machine_restored,undefined);
  const hints=[0,1,2,3,4].map(level=>e.hintText(p,level));
  assert.equal(hints[0],'');assert.equal(hints[4],p.hint);assert.equal(new Set(hints).size,5);
  e.hint();assert.equal(e.reset(),true);assert.deepEqual(e.state.puzzles.machine.configuration,m.initial(p.mechanics));
  configure(solution);touch('console');assert.equal(e.state.puzzles.machine.solved,true);
  assert.equal(observations.length,14);
 }
 e.advanceDialogue();touch('mentor');assert.equal(e.state.dialogue.id,'machine_after');e.advanceDialogue();
 assert.equal(e.state.flags.machine_understood,true);assert.equal(e.state.quests.machine_quest,'complete');
 assert.equal(e.tileFree(e.entities.get('machine_gate').x,9),true);
 const count=observations.length;saves.save(e);assert.ok(saves.load(e));assert.ok(saves.load(e));
 assert.equal(observations.length,count);assert.equal(e.state.xp,75);assert.equal(e.state.inventory.length,1);
 assert.equal(e.reset(),false);
 const forged=e.snapshot();forged.puzzles.machine.configuration.mode='missing';forged.puzzles.machine.effect={ok:true};
 e.restore(forged);assert.equal(e.state.puzzles.machine.solved,false);assert.equal(e.state.xp,0);
 assert.equal(e.state.flags.machine_restored,undefined);assert.equal(e.state.inventory.length,0);
 assert.equal(observations.length,count);
}
""", {'world':world,'cases':cases,'solution':mechanic.solve(p)['solution']})


def test_failed_effect_is_derived_from_configuration_not_saved_verdict():
    world = compile_world(blueprint(), SOURCE)
    node("""
const assert=require('node:assert/strict'),{WorldEngine,machineConfiguration:m}=require('./mindcrafted/engine/world/core.js');
const world=JSON.parse(require('node:fs').readFileSync(0,'utf8'));const e=new WorldEngine(world);
const saved=e.snapshot();saved.puzzles.machine.attempts=1;saved.puzzles.machine.effect={ok:true,rules:{budget:true},affectedControls:[]};
saved.puzzles.machine.solved=true;saved.flags.machine_restored=true;saved.xp=9999;
e.restore(saved);
assert.equal(e.state.puzzles.machine.solved,false);assert.equal(e.state.xp,0);
assert.deepEqual(e.state.puzzles.machine.effect,m.result(world.puzzles[0].mechanics,e.state.puzzles.machine.configuration));
""", world)
