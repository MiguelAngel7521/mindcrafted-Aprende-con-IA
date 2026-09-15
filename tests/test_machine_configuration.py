"""Machine contract, causal configuration rules, bounded search and generation."""
import asyncio
from copy import deepcopy
from itertools import product
import json
from pathlib import Path

import pytest

from mindcrafted.generator import machine_configuration as mechanic
from mindcrafted.generator.machine_configuration_demo import SOURCE, blueprint
from mindcrafted.generator.structured_schema import blueprint_response_schema, strict_response_schema
from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_knowledge import build_knowledge_graph
from mindcrafted.generator.world_package import quality_gate, runtime_probe
from mindcrafted.generator.world_pipeline import generate_campaign
from mindcrafted.generator.world_schema import MachineConfiguration
from test_node_connect_integration import node


@pytest.fixture(scope='module')
def machine_world():
    return compile_world(blueprint(), SOURCE, difficulty='hard')


def test_machine_contract_solver_and_knowledge(machine_world):
    report = validate_world(machine_world, SOURCE)
    assert report['ok'], report['errors']
    proof = report['solutions']['machine']
    assert proof == mechanic.solve(machine_world['puzzles'][0])
    assert proof['solutionCount'] == 3 and proof['evaluatedStates'] == 243
    assert proof['steps'] == 9 and proof['minChanges'] == 5
    assert proof['randomSuccessProbability'] == 3 / 108
    assert proof['randomTrials'] == 256 and proof['randomSuccessRate'] < .1
    assert len(proof['ablationWitnesses']) == 7
    assert proof['tradeoffs'][0]['preferred']
    assert runtime_probe(machine_world, report['walkthrough'])['observations'] == 7
    m = machine_world['puzzles'][0]['mechanics']
    for solution in [proof['solution']] + proof['alternativeSolutions']:
        assert mechanic.simulate(m, solution)['ok']
    for rule, witness in proof['ablationWitnesses'].items():
        assert not mechanic.simulate(m, witness)['ok']
        assert mechanic.simulate(m, witness, rule)['ok']
    graph = build_knowledge_graph(machine_world, SOURCE)
    assert len(graph['rules']) == 7
    assert all(r['evidenceIds'] for r in graph['rules'])
    assert any(path.startswith('/mechanics/configurationRules/') for r in graph['rules'] for b in r['bindings'] for path in b['mechanicPaths'])
    assert json.loads(Path('mindcrafted/engine/world/machine-configuration.schema.json').read_text()) == MachineConfiguration.model_json_schema()


def test_every_machine_state_and_rule_ablation_matches_javascript():
    m = blueprint()['puzzles'][0]['mechanics']
    domains = mechanic.domains(m)
    states = [dict(zip(domains, values)) for values in product(*domains.values())]
    ignored = [None] + [r['id'] for r in blueprint()['puzzles'][0]['knowledge']['requiredRules']]
    actual = node("""
const {machineConfiguration:m}=require('./mindcrafted/engine/world/machine-configuration.js');
const d=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(d.states.map(s=>d.ignored.map(r=>m.result(d.m,s,r)))));
""", {'m':m,'states':states,'ignored':ignored})
    assert actual == [[mechanic.simulate(m, state, rule) for rule in ignored] for state in states]


@pytest.mark.parametrize('mutation', [
    lambda m:m.update(javascript='openDoor()'),
    lambda m:m.update(schemaVersion=2),
    lambda m:m['machine'].update(id='constructor'),
    lambda m:m['slots'][0].update(id='mode'),
    lambda m:m['components'][0].update(id='durable'),
    lambda m:m['slots'][0].update(components=['volatile','missing']),
    lambda m:m['slots'][0].update(components=['volatile','volatile']),
    lambda m:m['components'].append({'id':'orphan','label':'Orphan'}),
    lambda m:m['parameters'][0].update(initial='missing'),
    lambda m:m['parameters'][0]['values'][0].update(id='online'),
    lambda m:m['parameters'][1]['values'][0].update(quantity=True),
    lambda m:m['configurationRules'][0]['then'].update(control='missing'),
    lambda m:m['configurationRules'][0]['then'].update(values=['unknown']),
    lambda m:m['configurationRules'][0]['when'].update(values=['online','online']),
    lambda m:m['configurationRules'][1]['left'].update(control='__proto__'),
    lambda m:m['configurationRules'][2].update(min=8,max=4),
    lambda m:m['configurationRules'][2].update(control='storage'),
    lambda m:m['parameters'][2]['values'][0].update(quantity=None),
    lambda m:m['configurationRules'][3]['terms'][0]['costs'].pop(),
    lambda m:m['configurationRules'][3]['terms'][0]['costs'][0].update(value='medium'),
    lambda m:m['configurationRules'][3]['terms'].append(deepcopy(m['configurationRules'][3]['terms'][0])),
    lambda m:m['configurationRules'][3]['terms'][0].update(control='missing'),
    lambda m:m['goals'][0].update(ruleId='missing'),
    lambda m:m['tradeoffs'][0].update(preferredValues=['missing']),
])
def test_machine_rejects_invalid_contract(mutation):
    p = deepcopy(blueprint()['puzzles'][0]); mutation(p['mechanics'])
    with pytest.raises(ValueError, match='SCHEMA_ERROR|REFERENCE_ERROR'):
        mechanic.solve(p)


def test_machine_bound_is_enforced_before_search(monkeypatch):
    p = blueprint()['puzzles'][0]; m = p['mechanics']
    for index in range(2):
        m['slots'].append(dict(m['slots'][0], id='extra_slot_'+str(index)))
    m['parameters'].append(dict(m['parameters'][0], id='extra_parameter'))
    assert len(list(product(*mechanic.domains(m).values()))) == 6561
    def forbidden(*args):
        pytest.fail('An unbounded blueprint must not start searching')
    monkeypatch.setattr(mechanic.finite, 'prove', forbidden)
    with pytest.raises(ValueError, match='SOLUTION_BOUNDS_ERROR'):
        mechanic.solve(p)


def test_reject_decorative_rules_unsolvable_and_wrong_step_bounds():
    p = blueprint()['puzzles'][0]
    p['mechanics']['configurationRules'].append({'kind':'required','ruleId':'ornament','condition':{'control':'mode','values':['maintenance','diagnostic','online']}})
    p['knowledge']['requiredRules'].append({'id':'ornament'})
    with pytest.raises(ValueError, match='EDUCATIONAL_COUPLING_ERROR.*ornament'):
        mechanic.solve(p)
    p = blueprint()['puzzles'][0]
    p['mechanics']['configurationRules'].append({'kind':'required','ruleId':'caching','condition':{'control':'cache','values':['off']}})
    with pytest.raises(ValueError, match='UNSOLVABLE'):
        mechanic.solve(p)
    p = blueprint()['puzzles'][0]
    p['difficulty'] = {'minSolutionSteps':1,'maxSolutionSteps':8,'randomSuccessProbabilityMax':.1}
    with pytest.raises(ValueError, match='DIFFICULTY_ERROR'):
        mechanic.solve(p)


def test_random_success_rejects_trivial_machine_even_with_causal_rules():
    p = blueprint()['puzzles'][0]
    p['difficulty'] = {'minSolutionSteps':1,'maxSolutionSteps':50,'randomSuccessProbabilityMax':.01}
    with pytest.raises(ValueError, match='RANDOM_SUCCESS_ERROR'):
        mechanic.solve(p)


@pytest.mark.parametrize('state', [None, [], 5, {}, {'storage':'durable'},
    {'storage':False,'link':'confirmed','mode':'online','cache':'off','memory':'small'},
    {'storage':'durable','link':'confirmed','mode':'online','cache':'off','memory':'small','extra':0}])
def test_machine_bad_state_is_rejected_by_both_simulators(state):
    m = blueprint()['puzzles'][0]['mechanics']
    with pytest.raises(ValueError, match='STATE_ERROR'):
        mechanic.simulate(m, state)
    node("""
const assert=require('node:assert/strict'),{machineConfiguration:m}=require('./mindcrafted/engine/world/machine-configuration.js');
const d=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
assert.throws(()=>m.result(d.m,d.state),/STATE_ERROR/);
""", {'m':m,'state':state})


@pytest.mark.parametrize('action', [None, {}, {'type':'openDoor'}, {'type':'control','controlId':'missing'},
    {'type':'control','controlId':'storage','setSolved':True}, {'type':'submit','reward':75}])
def test_machine_actions_cannot_execute_undeclared_commands(action):
    m = blueprint()['puzzles'][0]['mechanics']
    with pytest.raises(ValueError, match='ACTION_ERROR'):
        mechanic.transition(m, mechanic.initial(m), action)
    node("""
const assert=require('node:assert/strict'),{machineConfiguration:m}=require('./mindcrafted/engine/world/machine-configuration.js');
const d=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
assert.throws(()=>m.transition(d.m,m.initial(d.m),d.action),/ACTION_ERROR/);
""", {'m':m,'action':action})


def test_parameters_cycle_from_declared_initial_and_component_can_be_removed():
    m = blueprint()['puzzles'][0]['mechanics']
    m['parameters'][0]['initial'] = 'diagnostic'
    state = mechanic.initial(m)
    assert state['mode'] == 'diagnostic'
    for expected in ('online','maintenance','diagnostic'):
        state = mechanic.transition(m,state,{'type':'control','controlId':'mode'})
        assert state['mode'] == expected
    for expected in ('volatile','durable',None):
        state = mechanic.transition(m,state,{'type':'control','controlId':'storage'})
        assert state['storage'] == expected
    assert mechanic.transition(m,state,{'type':'reset'}) == mechanic.initial(m)


@pytest.mark.parametrize('source', [
    'La historia del arte estudia obras, artistas y periodos históricos.',
    'Configuración, componentes, parámetros, modos, dependencias y ajustes.',
    'El modo operativo requiere memoria. El modo  operativo requiere memoria.',
])
def test_source_eligibility_rejects_weak_or_repeated_relations(source):
    assert mechanic.eligibility(source)['status'] == 'SOURCE_TOO_WEAK_FOR_MACHINE_CONFIGURATION'


def test_source_gate_runs_before_provider_and_is_present_in_world_validation(machine_world, tmp_path):
    assert mechanic.eligibility(SOURCE)['status'] == 'PASS'
    async def forbidden(*args, **kwargs):
        pytest.fail('Source rejection must precede provider calls')
    weak = 'El material trata sobre poesía, su historia y las formas literarias de distintos periodos.'
    with pytest.raises(ValueError, match='SOURCE_TOO_WEAK_FOR_MACHINE_CONFIGURATION'):
        asyncio.run(generate_campaign(weak,tmp_path,generate=forbidden,parse_json=json.loads,archetype='machine_configuration'))
    world = deepcopy(machine_world)
    for r in world['puzzles'][0]['knowledge']['requiredRules']:
        r['evidence'] = weak
    report = validate_world(world, weak)
    assert not report['ok'] and 'SOURCE_TOO_WEAK_FOR_MACHINE_CONFIGURATION' in report['errors'][0]


def test_optional_tradeoff_never_changes_the_solution_set():
    p = blueprint()['puzzles'][0]
    before = mechanic.solve(p)
    p['mechanics']['tradeoffs'][0]['preferredValues'] = ['confirmed']
    after = mechanic.solve(p)
    assert after['solution'] == before['solution'] and after['solutionCount'] == before['solutionCount']
    assert after['tradeoffs'][0]['preferred'] is False


def test_unconstrained_physical_controls_are_rejected():
    p = blueprint()['puzzles'][0]
    p['mechanics']['parameters'].append(dict(p['mechanics']['parameters'][0], id='decoration'))
    with pytest.raises(ValueError, match='EDUCATIONAL_COUPLING_ERROR'):
        mechanic.solve(p)


def test_isolated_answer_selectors_are_not_a_machine():
    p = blueprint()['puzzles'][0]
    solution = mechanic.solve(p)['solution']
    p['mechanics']['configurationRules'] = [
        {'kind':'required', 'ruleId':control, 'condition':{'control':control, 'values':[value]}}
        for control, value in solution.items()]
    p['mechanics']['goals'] = [p['mechanics']['configurationRules'].pop()]
    p['knowledge']['requiredRules'] = [{'id':key} for key in solution]
    with pytest.raises(ValueError, match='EDUCATIONAL_COUPLING_ERROR'):
        mechanic.solve(p)


def test_machine_schema_is_available_in_real_structured_output_contract():
    schema = blueprint_response_schema('machine_configuration')
    wire = strict_response_schema(schema)
    assert schema['$defs']['BlueprintPuzzle']['properties']['mechanics'] == {'$ref':'#/$defs/MachineConfiguration'}
    assert 'ResourceBalance' not in schema['$defs'] and 'NodeConnect' not in schema['$defs']
    assert 'configurationRules' in json.dumps(wire)


def test_machine_generation_repairs_then_requires_real_gate(tmp_path):
    calls=[]; trace=[]
    async def model(prompt, system, **kwargs):
        calls.append(kwargs['step']); request=json.loads(prompt)
        if kwargs['step']=='world_blueprint':
            assert 'KNOWLEDGE DRIVES THE CONFIGURATION' in system
            assert kwargs['schema_version'].endswith('/machine-configuration-1')
            design=blueprint()
            if len(calls)==1:
                design['puzzles'][0]['mechanics']['configurationRules'][0]['then']['control']='missing'
            else:
                assert request['repair']['category']=='REFERENCE_ERROR'
            return json.dumps(design)
        assert all(request['tests'].values())
        return json.dumps({'approved':True,'scores':{k:24 for k in ('embodiedLearning','worldIntegration','interactionQuality','technicalSolvability')},'issues':[]})
    asyncio.run(generate_campaign(SOURCE,tmp_path,generate=model,parse_json=json.loads,archetype='machine_configuration',difficulty='hard',trace=trace))
    package=json.loads((tmp_path/'game.pkg.json').read_text())
    assert package['quality']['approved'] and package['quality']['e2e']['recovery']
    assert (tmp_path/'campaign/puzzles/machine.json').exists()
    assert calls==['world_blueprint','world_blueprint','world_judge']
    assert trace[-1]['stage']=='published'


def test_gate_supports_multiple_constraints_for_one_educational_rule():
    design = blueprint()
    p = design['puzzles'][0]
    for rule in p['mechanics']['configurationRules'] + p['mechanics']['goals']:
        rule['ruleId'] = 'consistency'
    p['knowledge']['requiredRules'] = [{'id':'consistency', 'skill':'configuration.consistency',
        'description':'El sistema funciona cuando toda su configuración es consistente.', 'evidence':SOURCE}]
    world = compile_world(design, SOURCE, difficulty='hard')
    report = quality_gate(world, SOURCE)
    assert all(report['checks'].values()), report['errors']


@pytest.mark.parametrize('mutation', [
    lambda w:w['puzzles'][0].update(runtime='iframe'),
    lambda w:w['puzzles'][0].update(resettable=False),
    lambda w:w['puzzles'][0]['failure'].update(autoReset=True),
    lambda w:w['puzzles'][0]['world'].update(anchorEntity='missing'),
    lambda w:w['puzzles'][0]['success'].update(openEntity='machine_storage'),
    lambda w:w['puzzles'][0]['knowledge']['requiredRules'][0].update(evidence='Esta evidencia no aparece en ningún lugar de la fuente.'),
    lambda w:w['regions'][0]['entities'].pop(3),
    lambda w:w['regions'][0]['entities'][3].update(type='machine_parameter'),
    lambda w:w['puzzles'][0]['mechanics']['configurationRules'][2].update(min=5,max=6),
])
def test_perfect_judge_cannot_override_machine_contract_failure(machine_world, mutation):
    world=deepcopy(machine_world);mutation(world)
    judge={'approved':True,'scores':{k:25 for k in ('embodiedLearning','worldIntegration','interactionQuality','technicalSolvability')},'issues':[]}
    report=quality_gate(world,SOURCE,judge=judge,run_probes=False)
    assert not report['approved'] and report['errors']
