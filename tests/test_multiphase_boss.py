"""Composite proofs must cover every successful branch, not just one walkthrough."""
from copy import deepcopy
import json

import pytest

from mindcrafted.generator.world_boss import compile_boss, validate_boss_world
from mindcrafted.generator.boss_demo import SOURCE, blueprint
from mindcrafted.generator.world import validate_world
from mindcrafted.generator.world_package import runtime_probe, quality_gate


def compile_two(design=None):
    design=design or blueprint()
    return compile_boss(design,SOURCE,prior_skills=design['requiredSkills'])


def test_two_phases_solver_propagates_every_outcome_and_real_runtime():
    world=compile_two();report=validate_world(world,SOURCE)
    assert report['ok'],report['errors']
    proof=report['boss']['archive_recovery']
    variants=[p for p in proof['variantProofs'] if p['phaseId']=='distribution']
    assert {p['shared']['executor_budget'] for p in variants}=={4,5}
    assert {p['solutionCount'] for p in variants}=={2,6}
    assert proof['recoverable'] and proof['causalityWitnesses']
    assert runtime_probe(world,report['walkthrough'])['ok']


def test_boss_cannot_introduce_required_knowledge():
    b=blueprint()
    with pytest.raises(ValueError,match='BOSS_CONCEPT_NOT_PREVIOUSLY_INTRODUCED'):
        compile_boss(b,SOURCE,prior_skills=b['requiredSkills'][1:])


def test_single_bad_winning_branch_rejects_whole_boss():
    b=blueprint()
    b['sharedState'][0]['values']=[1,4]
    b['phases'][0]['exports'][0]['cases'][1]['value']=1
    with pytest.raises(ValueError,match='BOSS_CROSS_PHASE_UNSOLVABLE'):
        compile_two(b)


def test_decorative_shared_state_is_rejected():
    b=blueprint()
    b['phases'][0]['exports'][0]['cases'][1]['value']=4
    with pytest.raises(ValueError,match='BOSS_DECORATIVE_SHARED_STATE'):
        compile_two(b)


@pytest.mark.parametrize('mutation', ['cycle','missing_next','unknown_variable','future_input','unknown_control','ungrounded','bad_archetype','duplicate_phase','duplicate_puzzle'])
def test_boss_contract_rejects_invalid_composition(mutation):
    b=blueprint()
    if mutation=='cycle':b['phases'][1]['next']='connections'
    if mutation=='missing_next':b['phases'][0]['next']='missing'
    if mutation=='unknown_variable':b['phases'][1]['bindings'][0]['variable']='missing'
    if mutation=='future_input':b['phases'][0]['bindings']=deepcopy(b['phases'][1]['bindings'])
    if mutation=='unknown_control':b['phases'][0]['exports'][0]['controlId']='missing'
    if mutation=='ungrounded':b['phases'][0]['exports'][0]['evidence']='Una regla inventada que nunca aparece en el material.'
    if mutation=='bad_archetype':b['phases'][0]['puzzle']['mechanics']['archetype']='BossNodeConnect'
    if mutation=='duplicate_phase':b['phases'][1]['id']=b['phases'][0]['id']
    if mutation=='duplicate_puzzle':b['phases'][1]['puzzle']['id']=b['phases'][0]['puzzle']['id']
    with pytest.raises(ValueError):compile_two(b)


def test_perfect_judge_cannot_override_cross_phase_failure():
    world=compile_two()
    world['bosses'][0]['sharedState'][0]['values']=[1,4]
    world['bosses'][0]['phases'][0]['exports'][0]['cases'][1]['value']=1
    judge={'approved':True,'scores':{k:25 for k in ('embodiedLearning','worldIntegration','interactionQuality','technicalSolvability')},'issues':[]}
    report=quality_gate(world,SOURCE,judge=judge,run_probes=False)
    assert not report['approved'] and not report['checks']['boss']
    assert 'BOSS_CROSS_PHASE_UNSOLVABLE' in report['errors'][0]


def test_three_phase_shared_memory_and_cache_both_have_causal_witnesses():
    from mindcrafted.generator.boss_demo import THREE_PHASE_SOURCE,three_phase_blueprint
    b=three_phase_blueprint();world=compile_boss(b,THREE_PHASE_SOURCE,prior_skills=b['requiredSkills'])
    proof=validate_boss_world(world,THREE_PHASE_SOURCE)['archive_recovery']
    assert len(proof['variantProofs'])==7
    assert proof['reachableFinalStates']==4
    assert {w['variable'] for w in proof['causalityWitnesses']}=={'memory_budget','executor_budget'}
    assert proof['evaluatedStates']==3558
    assert all(selection['status']=='SELECTED' for selection in proof['mechanicSelection'].values())


def test_four_phase_contract_reuses_archetype_without_another_runtime():
    from mindcrafted.generator.boss_demo import THREE_PHASE_SOURCE,three_phase_blueprint
    b=three_phase_blueprint();third=b['phases'][-1];fourth=deepcopy(third)
    fourth['id']='backup';fourth['puzzle']['id']='backup';third['next']='backup'
    extra='En la segunda pasada, Audio asignado a Rápido permite cuatro unidades; Audio asignado a Auxiliar permite cinco unidades.'
    source=THREE_PHASE_SOURCE+'\n'+extra
    third['exports']=[{'variable':'backup_budget','kind':'configuration_value','controlId':'audio',
                      'cases':[{'when':'fast','value':4},{'when':'aux','value':5}],
                      'ruleId':'latency','evidence':extra}]
    fourth['bindings'][0].update(variable='backup_budget',evidence=extra)
    b['phases'].append(fourth);b['sharedState'].append({'id':'backup_budget','label':'Reserva de segunda pasada','values':[4,5]})
    world=compile_boss(b,source,prior_skills=b['requiredSkills']);report=validate_world(world,source)
    assert len(world['puzzles'])==4 and report['ok']
    assert runtime_probe(world,report['walkthrough'])['ok']
    b['phases'].append(deepcopy(fourth))
    with pytest.raises(ValueError):compile_boss(b,source,prior_skills=b['requiredSkills'])


def test_solution_budget_and_branch_limit_are_enforced(monkeypatch):
    from mindcrafted.generator import world_boss as boss
    monkeypatch.setattr(boss,'MAX_EVALUATED_STATES',2048)
    with pytest.raises(ValueError,match='BOSS_SOLUTION_BOUNDS'):compile_two()
    monkeypatch.setattr(boss,'MAX_EVALUATED_STATES',32768)
    monkeypatch.setattr(boss,'MAX_VARIANTS',1)
    with pytest.raises(ValueError,match='BOSS_SOLUTION_BOUNDS'):compile_two()


@pytest.mark.parametrize('mutation',['reward','completion','prerequisite','policy'])
def test_compiled_boss_cannot_bypass_rewards_transitions_or_recovery(mutation):
    world=compile_two()
    if mutation=='reward':world['puzzles'][-1]['success']['xp']+=1
    if mutation=='completion':world['bosses'][0]['completion']['flag']='unearned'
    if mutation=='prerequisite':world['puzzles'][-1]['prerequisites']=[]
    if mutation=='policy':world['bosses'][0]['failurePolicy']='checkpoint'
    report=validate_world(world,SOURCE)
    assert not report['ok'] and not report['checks']['boss']


def test_boss_schema_export_is_exact_and_rejects_executable_bindings():
    from pathlib import Path
    from mindcrafted.generator.world_schema import BOSS_BLUEPRINT_SCHEMA,BossBlueprint
    assert json.loads(Path('mindcrafted/engine/world/boss-blueprint.schema.json').read_text())==BOSS_BLUEPRINT_SCHEMA
    b=blueprint();b['phases'][1]['bindings'][0]['expression']='openDoor()'
    with pytest.raises(ValueError):BossBlueprint.model_validate(b)


def test_manual_composition_agrees_with_auto_selector_on_each_objective():
    from mindcrafted.generator.boss_demo import THREE_PHASE_SOURCE,three_phase_blueprint
    from mindcrafted.generator.knowledge_features import build_structure_graph,objective_from_evidence
    from mindcrafted.generator.mechanic_selector import MechanicSelector
    graph=build_structure_graph(THREE_PHASE_SOURCE)
    for phase in three_phase_blueprint()['phases']:
        p=phase['puzzle']
        objective=objective_from_evidence(graph,p['objective'],[r['evidence'] for r in p['knowledge']['requiredRules']],objective_id=phase['id'])
        selection=MechanicSelector().select(graph,THREE_PHASE_SOURCE,objective)
        assert selection['selectedMechanic']==p['mechanics']['archetype']
