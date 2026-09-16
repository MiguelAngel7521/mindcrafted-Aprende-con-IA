"""Selector → blueprint → compiler → deterministic gate → same-canvas campaign."""
import asyncio
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator

from mindcrafted.generator import node_connect_demo as nodes, resource_balance_demo as resources, machine_configuration_demo as machines
from mindcrafted.generator.knowledge_features import LearningObjective, build_structure_graph, objective_from_evidence
from mindcrafted.generator.mechanic_selector import generation_contract, verify_objective_binding
from mindcrafted.generator.selector_demo import SOURCE, selected_blueprint
from mindcrafted.generator.structured_schema import blueprint_response_schema, strict_response_schema
from mindcrafted.generator.world import compile_world
from mindcrafted.generator.world_campaign import assemble_campaign, write_campaign
from mindcrafted.generator.world_package import CHECKS, make_package, quality_gate
from mindcrafted.generator.world_pipeline import generate_campaign
from test_mechanic_selector import AMBIGUOUS


def judge():
    return {'approved':True,'scores':{k:25 for k in ('embodiedLearning','worldIntegration','interactionQuality','technicalSolvability')},'issues':[]}


@pytest.mark.parametrize('module', [nodes,resources,machines])
def test_quality_gate_rejects_ineligible_even_with_perfect_judge(module):
    world=compile_world(module.blueprint(),module.SOURCE,difficulty='hard')
    source='El material describe colores, emociones y personajes de una obra literaria.'
    for p in world['puzzles']:
        for rule in p['knowledge']['requiredRules']: rule['evidence']=source
    report=quality_gate(world,source,judge=judge(),run_probes=False)
    assert report['approved'] is False and report['checks']['mechanicEligibility'] is False
    evidence=report['mechanicEligibility'][world['puzzles'][0]['id']]
    assert evidence['status'].startswith('SOURCE_TOO_WEAK_FOR_')
    assert evidence['eligible'] is False
    assert 'mechanicEligibility' in CHECKS


def test_generator_schema_excludes_mechanics_outside_allowed_set():
    allowed=['resource_balance','machine_configuration']
    schema=blueprint_response_schema(allowed_archetypes=allowed)
    strict=strict_response_schema(schema)
    design=resources.blueprint()
    design["puzzles"][0]["role"]="challenge"
    for current in (schema,strict):
        assert not list(Draft202012Validator(current).iter_errors(design))
        assert list(Draft202012Validator(current).iter_errors(nodes.blueprint()))
    with pytest.raises(ValueError,match='Invalid allowed mechanics'):
        blueprint_response_schema(allowed_archetypes=[])
    with pytest.raises(ValueError,match='Invalid allowed mechanics'):
        blueprint_response_schema('node_connect',allowed_archetypes=allowed)


@pytest.mark.parametrize('source,status', [('La historia describe personajes, colores y emociones en las obras de un periodo literario.', 'NO_ELIGIBLE_MECHANIC'),
                                          (AMBIGUOUS,'AMBIGUOUS_MECHANIC_SELECTION')])
def test_auto_refuses_before_any_provider_call(source,status,tmp_path):
    async def forbidden(*args,**kwargs):
        pytest.fail('No provider call without a verified choice')
    with pytest.raises(ValueError,match=status):
        asyncio.run(generate_campaign(source,tmp_path,generate=forbidden,parse_json=json.loads,archetype='AUTO'))


@pytest.mark.parametrize('module', [nodes,resources,machines])
def test_auto_contract_with_mock_model_and_real_quality_gate(module,tmp_path):
    archetype=module.blueprint()['puzzles'][0]['mechanics']['archetype']
    calls=[]
    async def model(prompt,system,**kwargs):
        calls.append(kwargs['step']); request=json.loads(prompt)
        if kwargs['step']=='world_blueprint':
            assert 'AI MAY SUGGEST' in system
            assert request['recommendedMechanic']==archetype
            assert archetype in request['eligibleMechanics']
            assert request['allowedMechanics']==[archetype]
            assert request['learningObjective']['relationIds']
            assert 'NodeConnect' in kwargs['response_schema']['$defs'] if archetype=='node_connect' else 'NodeConnect' not in kwargs['response_schema']['$defs']
            return json.dumps(module.blueprint())
        assert request['tests']['mechanicEligibility']
        return json.dumps(judge())
    asyncio.run(generate_campaign(module.SOURCE,tmp_path,generate=model,parse_json=json.loads,archetype='AUTO',difficulty='hard'))
    package=json.loads((tmp_path/'game.pkg.json').read_text())
    assert calls==['world_blueprint','world_judge']
    assert package['quality']['approved']
    assert package['quality']['mechanicSelection']['selectedMechanic']==archetype
    assert package['quality']['e2e']['recovery'] and package['quality']['e2e']['reload']


def test_scope_is_verified_separately_from_mechanic_and_grounding():
    graph=build_structure_graph(SOURCE)
    p=nodes.blueprint()['puzzles'][0]
    objective=objective_from_evidence(graph,p['objective'],[r['evidence'] for r in p['knowledge']['requiredRules']],objective_id='topology')
    verify_objective_binding(p,graph,objective)
    unrelated=deepcopy(p)
    unrelated['knowledge']['requiredRules'][0]['evidence']=resources.SOURCE.splitlines()[1]
    with pytest.raises(ValueError,match='OBJECTIVE_SCOPE_ERROR'):
        verify_objective_binding(unrelated,graph,objective)


def test_selected_three_objectives_compile_gate_campaign_and_browser(tmp_path):
    design,evidence=selected_blueprint()
    expected=['node_connect','resource_balance','machine_configuration']
    assert [s['selectedMechanic'] for s in evidence['selections']]==expected
    world=compile_world(design,SOURCE,difficulty='hard')
    report=quality_gate(world,SOURCE,screenshot=tmp_path/'selector-world.png')
    assert all(report['checks'].values()),report['errors']
    assert report['e2e']['recovery'] and report['e2e']['reload']
    assert all(r['eligible'] for r in report['mechanicEligibility'].values())
    # Keep the production approval boundary: deterministic fixture has no real AI judge.
    assert report['approved'] is False
    package=make_package(world,SOURCE,'selected_objectives')
    package['developmentDemo']=True
    package['quality']=report
    second_world=compile_world(machines.blueprint(),machines.SOURCE,difficulty='hard')
    second=make_package(second_world,machines.SOURCE,'repeat_ids')
    second['developmentDemo']=True
    campaign=assemble_campaign([package,second],'selected_campaign',development=True)
    manifest=write_campaign(campaign,tmp_path/'campaign',screenshot=tmp_path/'selector-campaign.png')
    assert manifest['checks']['ok'] and manifest['checks']['regions']==2
    assert manifest['checks']['recovery'] and manifest['checks']['reload']
    assert [p['archetype'] for p in campaign['campaign']['regions'][0]['world']['puzzles']]==expected
    (tmp_path/'selection.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))


@pytest.mark.parametrize('mismatch', ['archetype','objective'])
def test_fallback_cannot_escape_selected_mechanic_or_objective(mismatch,tmp_path,monkeypatch):
    from mindcrafted.generator import world_pipeline
    world=compile_world(nodes.blueprint(),SOURCE,difficulty='hard')
    package=make_package(world,SOURCE)
    package['quality']={'approved':True,'worldHash':package['config']['worldHash'],'judge':judge()}
    path=tmp_path/'game.pkg.json'
    original=json.dumps(package);path.write_text(original)
    def forbidden(*args,**kwargs):
        pytest.fail('Unrelated fallback must be rejected before probes or publication')
    monkeypatch.setattr(world_pipeline,'quality_gate',forbidden)
    graph=build_structure_graph(SOURCE)
    p=machines.blueprint()['puzzles'][0]
    objective=objective_from_evidence(graph,p['objective'],[r['evidence'] for r in p['knowledge']['requiredRules']],objective_id='configuration')
    selection={'recommendedMechanic':'resource_balance' if mismatch=='archetype' else 'node_connect'}
    error='FALLBACK_MECHANIC_MISMATCH' if mismatch=='archetype' else 'OBJECTIVE_SCOPE_ERROR'
    with pytest.raises(ValueError,match=error):
        asyncio.run(world_pipeline.build_safe_fallback(SOURCE,tmp_path,'rejected candidates',selection=selection,
                                                       objective=objective if mismatch=='objective' else None,
                                                       structure_graph=graph))
    assert path.read_text()==original
