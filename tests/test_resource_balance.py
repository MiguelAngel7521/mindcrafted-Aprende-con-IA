"""Resource contract, exhaustive cross-runtime arbitration and recoverable actions."""
import asyncio
from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import random

import pytest

from mindcrafted.generator import resource_balance as mechanic
from mindcrafted.generator.resource_balance_demo import SOURCE, blueprint
from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_knowledge import build_knowledge_graph
from mindcrafted.generator.world_package import quality_gate, runtime_probe
from mindcrafted.generator.world_pipeline import generate_campaign
from mindcrafted.generator.world_schema import ResourceBalance
from test_node_connect_integration import node


@pytest.fixture(scope="module")
def resource_world():
    return compile_world(blueprint(), SOURCE, difficulty="hard")


def test_resource_proof_and_world_contract(resource_world):
    report = validate_world(resource_world, SOURCE)
    assert report["ok"], report["errors"]
    proof = report["solutions"]["balance"]
    assert proof == mechanic.solve(resource_world["puzzles"][0])
    assert proof["solutionCount"] == 2 and proof["steps"] == 8
    assert proof["randomSuccessProbability"] == 2 / 81
    assert proof["randomTrials"] == 256 and proof["randomSuccessRate"] < .1
    assert set(proof["ablationWitnesses"]) == {"latency", "capacity", "service"}
    assert runtime_probe(resource_world, report["walkthrough"])["observations"] == 3
    graph = build_knowledge_graph(resource_world, SOURCE)
    assert any(path.startswith('/mechanics/allocationRules/') for r in graph['rules'] for b in r['bindings'] for path in b['mechanicPaths'])
    schema = Path('mindcrafted/engine/world/resource-balance.schema.json')
    assert json.loads(schema.read_text()) == ResourceBalance.model_json_schema()


def test_every_assignment_and_ablation_matches_javascript():
    m = blueprint()['puzzles'][0]['mechanics']
    domains = mechanic.domains(m)
    states = [dict(zip(domains, values)) for values in product(*domains.values())]
    ignored = [None, 'latency', 'capacity', 'service']
    actual = node("""
const {resourceBalance: m} = require('./mindcrafted/engine/world/resource-balance.js');
const data = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(data.states.map(s => data.ignored.map(r => m.result(data.m,s,r)))));
""", {'m': m, 'states': states, 'ignored': ignored})
    assert actual == [[mechanic.simulate(m, s, r) for r in ignored] for s in states]


@pytest.mark.parametrize('mutation', [
    lambda m: m.update(javascript='alert(1)'),
    lambda m: m.update(schemaVersion=2),
    lambda m: m['loads'][0].update(id='constructor'),
    lambda m: m['loads'][0].update(id='archive'),
    lambda m: m['loads'][0].update(amount=True),
    lambda m: m['allocationRules'][0]['allowed'][0].update(targetKind='missing'),
    lambda m: m['allocationRules'][1]['limits'][0].update(target='missing'),
    lambda m: m['allocationRules'][1]['limits'][0].update(min=6, max=4),
    lambda m: m['allocationRules'][1]['limits'].pop(),
    lambda m: m['goals'][0].update(ruleId='missing'),
])
def test_invalid_resource_contract(mutation):
    p = deepcopy(blueprint()['puzzles'][0]); mutation(p['mechanics'])
    with pytest.raises(ValueError, match='SCHEMA_ERROR|REFERENCE_ERROR|SOLUTION_BOUNDS_ERROR'):
        mechanic.solve(p)


@pytest.mark.parametrize('state', [None, {}, [], 0, {'audio':'missing'}, {'audio':True, 'control':None, 'report':None, 'copy':None}])
def test_invalid_state_rejected_on_both_runtimes(state):
    m = blueprint()['puzzles'][0]['mechanics']
    with pytest.raises(ValueError, match='STATE_ERROR'):
        mechanic.simulate(m, state)
    node("""
const assert=require('node:assert/strict'), {resourceBalance:m}=require('./mindcrafted/engine/world/resource-balance.js');
const d=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
assert.throws(()=>m.result(d.m,d.state),/STATE_ERROR/);
""", {'m':m,'state':state})


def test_reject_unsolvable_and_decorative_resource_rules():
    p = blueprint()['puzzles'][0]
    p['mechanics']['loads'][0]['amount'] = 100
    with pytest.raises(ValueError, match='UNSOLVABLE'):
        mechanic.solve(p)
    p = blueprint()['puzzles'][0]
    p['mechanics']['allocationRules'].append({'kind':'capacity','ruleId':'decoration','limits':[{'target':'archive','min':0,'max':100}]})
    p['knowledge']['requiredRules'].append({'id':'decoration'})
    with pytest.raises(ValueError, match='EDUCATIONAL_COUPLING_ERROR'):
        mechanic.solve(p)


def test_resource_source_eligibility_is_local_and_rejects_keyword_lists():
    assert mechanic.eligibility(SOURCE)['status'] == 'PASS'
    assert mechanic.eligibility('Historia y poesía. Capacidad, recurso, carga, presupuesto.')['status'] == 'SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE'
    async def forbidden(*args, **kwargs):
        pytest.fail('A weak source must not call the provider')
    with pytest.raises(ValueError, match='SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE'):
        asyncio.run(generate_campaign('Historia y poesía son temas amplios para estudiar en la universidad.', '/tmp/unused',
                                     generate=forbidden, parse_json=json.loads, archetype='resource_balance'))


def test_random_resource_actions_recover_and_reload_without_duplicate_rewards(resource_world):
    rng = random.Random(314159)
    m = resource_world['puzzles'][0]['mechanics']
    trials = []
    for _ in range(256):
        state = mechanic.initial(m); actions = []
        for _ in range(rng.randint(1, 32)):
            action = {'type':'control','controlId':rng.choice(list(state))}
            actions.append(action); state = mechanic.transition(m, state, action)
        trials.append({'actions':actions,'state':state,'result':mechanic.simulate(m, state)})
    assert sum(t['result']['ok'] for t in trials) / len(trials) < .1
    proof = mechanic.solve(resource_world['puzzles'][0])
    node("""
const assert=require('node:assert/strict'),{WorldEngine}=require('./mindcrafted/engine/world/core.js');
const {world,trials,proof}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for(const trial of trials){
 let e=new WorldEngine(world); const p=world.puzzles[0],pid=p.id;
 assert.equal(e.interact('balance_audio'),false);
 function touch(id){const n=e.entities.get(id);e.state.player={x:n.x-1,y:n.y};assert.equal(e.interact(id),true);}
 touch('balance_mentor');e.advanceDialogue();
 for(const a of trial.actions) touch('balance_'+a.controlId);
 assert.deepEqual(e.state.puzzles[pid].configuration,trial.state);
 let partial=e.snapshot();e=new WorldEngine(world);e.restore(partial);
 assert.deepEqual(e.state.puzzles[pid].configuration,trial.state);
 touch('balance_console');assert.equal(e.state.puzzles[pid].solved,trial.result.ok);
 if(!trial.result.ok){
  assert.deepEqual(e.state.puzzles[pid].configuration,trial.state);
  e.restore(e.snapshot()); assert.deepEqual(e.state.puzzles[pid].effect,trial.result);
  e.hint();assert.equal(e.reset(),true);
  for(const a of proof.actions)touch(a.type==='submit'?'balance_console':'balance_'+a.controlId);
 }
 assert.equal(e.state.puzzles[pid].solved,true);
 e.advanceDialogue();touch('balance_mentor');assert.equal(e.state.dialogue.id,'balance_after');e.advanceDialogue();
 const observations=[];e.events.on('learning.observation',o=>observations.push(o));
 e.restore(e.snapshot());e.restore(e.snapshot());
 assert.equal(e.state.xp,75);assert.equal(e.state.inventory.length,1);assert.equal(observations.length,0);
 assert.equal(e.state.quests.balance_quest,'complete');assert.equal(e.state.flags.balance_understood,true);
 const forged=e.snapshot();forged.puzzles.balance.configuration.audio='missing';
 e.restore(forged);assert.equal(e.state.puzzles.balance.solved,false);assert.equal(e.state.xp,0);
}
""", {'world':resource_world,'trials':trials,'proof':proof})


def test_resource_generation_repairs_with_real_gate(tmp_path):
    calls=[]
    async def model(prompt, system, **kwargs):
        calls.append(kwargs['step']); request=json.loads(prompt)
        if kwargs['step']=='world_blueprint':
            assert 'resource_balance' in system and 'ResourceBalance' in json.dumps(request['schema'])
            design=blueprint()
            if len(calls)==1: design['puzzles'][0]['mechanics']['loads'][0]['amount']=100
            else: assert request['repair']['category']=='UNSOLVABLE'
            return json.dumps(design)
        assert all(request['tests'].values())
        return json.dumps({'approved':True,'scores':{k:24 for k in ('embodiedLearning','worldIntegration','interactionQuality','technicalSolvability')},'issues':[]})
    asyncio.run(generate_campaign(SOURCE,tmp_path,generate=model,parse_json=json.loads,archetype='resource_balance',difficulty='hard'))
    package=json.loads((tmp_path/'game.pkg.json').read_text())
    assert package['quality']['approved'] and package['quality']['e2e']['recovery']
    assert calls==['world_blueprint','world_blueprint','world_judge']


@pytest.mark.parametrize('mutation', [
    lambda w:w['puzzles'][0]['mechanics']['loads'][0].update(amount=100),
    lambda w:w['puzzles'][0].update(runtime='iframe'),
    lambda w:w['puzzles'][0]['world'].update(anchorEntity='missing'),
    lambda w:w['puzzles'][0]['success'].update(openEntity='balance_audio'),
    lambda w:w['regions'][0]['entities'].pop(3),
    lambda w:w['regions'][0]['entities'][3].update(type='resource_target'),
])
def test_perfect_judge_cannot_override_resource_failure(resource_world,mutation):
    world=deepcopy(resource_world);mutation(world)
    judge={'approved':True,'scores':{k:25 for k in ('embodiedLearning','worldIntegration','interactionQuality','technicalSolvability')},'issues':[]}
    report=quality_gate(world,SOURCE,judge=judge,run_probes=False)
    assert not report['approved'] and report['errors']


def test_resource_physical_object_bound_is_enforced():
    p = blueprint()['puzzles'][0]
    p['mechanics']['loads'].extend([dict(p['mechanics']['loads'][0], id='extra1'), dict(p['mechanics']['loads'][0], id='extra2')])
    p['mechanics']['targets'].append({'id':'fourth','label':'Fourth','kind':'batch'})
    with pytest.raises(ValueError, match='SOLUTION_BOUNDS_ERROR'):
        mechanic.solve(p)
