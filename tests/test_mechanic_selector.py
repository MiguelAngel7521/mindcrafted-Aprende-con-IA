"""Structural evidence and objective decisions are deterministic, bounded and fail closed."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random

import pytest

from mindcrafted.generator import node_connect, resource_balance, machine_configuration
from mindcrafted.generator import node_connect_demo as nodes, resource_balance_demo as resources, machine_configuration_demo as machines
from mindcrafted.generator.knowledge_features import (LearningObjective, build_structure_graph, extract_features,
                                                     objective_from_evidence, validate_structure_graph)
from mindcrafted.generator.mechanic_selector import (MechanicSelector, eligibility, generation_contract,
                                                    puzzle_eligibility)
from mindcrafted.generator.selector_demo import SOURCE, selected_blueprint

OBJECTIVE = LearningObjective('objective', 'Comprender la estructura de este material')
AMBIGUOUS = ('El modo de carga requiere una capacidad de cuatro unidades.\n'
             'El parámetro de recurso requiere un presupuesto de ocho unidades.')


def select(source, objective=OBJECTIVE, **kwargs):
    return MechanicSelector().select(build_structure_graph(source), source, objective, **kwargs)


@pytest.mark.parametrize('module,expected', [(nodes,'node_connect'),(resources,'resource_balance'),(machines,'machine_configuration')])
def test_controlled_clear_fixtures(module, expected):
    result = select(module.SOURCE)
    assert result['status'] == 'SELECTED' and result['selectedMechanic'] == expected
    assert expected in result['eligibleMechanics']
    assert result['margin'] is None or result['margin'] > .05
    assert all(c['reasons'] for c in result['candidates'])


@pytest.mark.parametrize('module,archetype,source', [
    (node_connect,'node_connect',nodes.SOURCE),
    (resource_balance,'resource_balance',resources.SOURCE),
    (machine_configuration,'machine_configuration',machines.SOURCE)])
def test_archetypes_use_identical_common_contract(module, archetype, source):
    assert module.eligibility(source) == eligibility(source, archetype)
    candidate = next(c for c in select(source)['candidates'] if c['archetype'] == archetype)
    assert module.eligibility(source)['score'] == candidate['score']
    assert candidate['eligible'] and candidate['status'] == 'PASS'


@pytest.mark.parametrize('source', ['', 'Configuración, componentes, parámetros, modos, recursos y capacidad de 4.',
                                      'Un poema evoca paisajes, colores, estaciones y sensaciones.',
                                      'El modo requiere memoria. El modo   requiere memoria.'])
def test_no_eligible_mechanic_never_defaults(source):
    result = select(source)
    assert result['status'] == 'NO_ELIGIBLE_MECHANIC'
    assert result['selectedMechanic'] is None and result['eligibleMechanics'] == []
    assert all(c['score'] == 0 for c in result['candidates'])
    with pytest.raises(ValueError, match='NO_ELIGIBLE_MECHANIC'):
        generation_contract(build_structure_graph(source), source, OBJECTIVE)


def test_features_are_relations_with_endpoints_and_exact_grounding():
    graph = build_structure_graph(machines.SOURCE)
    assert graph['format'] == 'mindcrafted-educational-structure'
    features = extract_features(graph, machines.SOURCE, OBJECTIVE)
    assert features['configurationCount'] >= 6
    assert features['compatibilityCount'] == 1
    assert features['parameterCount'] >= 4 and features['componentCount'] >= 3
    assert features['dependencyCount'] >= 3 and features['capacityCount'] >= 1
    concepts = {c['id']:c for c in graph['concepts']}
    for r in graph['relations']:
        evidence = r['evidence']
        assert machines.SOURCE[evidence['start']:evidence['end']] == evidence['quote']
        assert concepts[r['subject']]['label'] in evidence['quote']
        assert concepts[r['object']]['label'] in evidence['quote']
        assert r['predicate'] in evidence['quote']


@pytest.mark.parametrize('mutation', ['hash','quote','offset','tag','endpoint','new_relation','count'])
def test_invented_or_tampered_graphs_cannot_gain_eligibility(mutation):
    graph = build_structure_graph(nodes.SOURCE)
    if mutation == 'hash': graph['sourceHash'] = 'f'*64
    if mutation == 'quote': graph['relations'][0]['evidence']['quote'] = 'made up'
    if mutation == 'offset': graph['relations'][0]['evidence']['start'] += 1
    if mutation == 'tag': graph['relations'][0]['features'].append('resource')
    if mutation == 'endpoint': graph['relations'][0]['object'] = 'unknown'
    if mutation == 'new_relation': graph['relations'].append(deepcopy(graph['relations'][0]))
    if mutation == 'count': graph['factCount'] = 9999
    with pytest.raises(ValueError, match='GROUNDING_ERROR'):
        MechanicSelector().select(graph, nodes.SOURCE, OBJECTIVE)


def test_quantities_without_budget_and_budget_without_quantities_are_insufficient_for_resources():
    for source in ('La carga requiere un recurso adecuado. El recurso requiere otra carga.',
                   'La carga requiere capacidad limitada. El recurso requiere presupuesto reducido.'):
        result = select(source)
        assert 'resource_balance' not in result['eligibleMechanics']
        assert eligibility(source,'resource_balance')['status'] == 'SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE'


def test_ambiguity_has_candidates_and_no_recommendation():
    result = select(AMBIGUOUS)
    assert result['status'] == 'AMBIGUOUS_MECHANIC_SELECTION'
    assert result['selectedMechanic'] is None and result['recommendedMechanic'] is None
    assert result['margin'] == 0
    assert {'resource_balance','machine_configuration'} <= set(result['eligibleMechanics'])
    with pytest.raises(ValueError, match='AMBIGUOUS_MECHANIC_SELECTION'):
        generation_contract(build_structure_graph(AMBIGUOUS), AMBIGUOUS, OBJECTIVE)


def test_objective_intent_never_overcomes_weak_source_or_small_margin():
    # The explicit intent adds 0.04: a tie remains ambiguous under the 0.05 margin.
    result = select(AMBIGUOUS, replace(OBJECTIVE,intent='configure'))
    assert result['status'] == 'AMBIGUOUS_MECHANIC_SELECTION' and result['margin'] == .04
    assert select(nodes.SOURCE, replace(OBJECTIVE,intent='configure'))['selectedMechanic'] == 'node_connect'


def test_per_objective_subgraph_produces_three_mechanics_from_same_source():
    blueprint, evidence = selected_blueprint()
    assert [s['selectedMechanic'] for s in evidence['selections']] == ['node_connect','resource_balance','machine_configuration']
    assert len({s['sourceHash'] for s in evidence['selections']}) == 1
    groups = [set(s['features']['relationIds']) for s in evidence['selections']]
    assert not groups[0] & groups[1] and not groups[1] & groups[2]
    assert [p['mechanics']['archetype'] for p in blueprint['puzzles']] == [s['selectedMechanic'] for s in evidence['selections']]
    # Misleading objective wording cannot import relationships from another section.
    objective = LearningObjective('scoped','Configure a router',tuple(groups[0]),intent='configure')
    assert select(SOURCE,objective)['selectedMechanic'] == 'node_connect'


def test_concept_scope_is_induced_subgraph_and_empty_scope_is_empty():
    graph = build_structure_graph(nodes.SOURCE)
    relations = graph['relations'][:2]
    ids = tuple({r[k] for r in relations for k in ('subject','object')})
    result = select(nodes.SOURCE,replace(OBJECTIVE,concept_ids=ids))
    assert result['features']['relationCount'] == 2
    assert result['selectedMechanic'] == 'node_connect'
    assert select(nodes.SOURCE,replace(OBJECTIVE,relation_ids=()))['status'] == 'NO_ELIGIBLE_MECHANIC'


@pytest.mark.parametrize('field', ['relation_ids','concept_ids'])
def test_objective_references_fail_closed(field):
    with pytest.raises(ValueError, match='REFERENCE_ERROR'):
        select(nodes.SOURCE,replace(OBJECTIVE,**{field:('missing',)}))


def test_evidence_scope_does_not_borrow_other_objective_relations():
    puzzle = deepcopy(resources.blueprint()['puzzles'][0])
    for rule in puzzle['knowledge']['requiredRules']:
        rule['evidence'] = nodes.SOURCE.splitlines()[0]
    result = puzzle_eligibility(puzzle, SOURCE)
    assert not result['eligible']
    assert result['status'] == 'SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE'


def test_forcing_compatible_is_explicit_and_incompatible_is_error():
    result = select(resources.SOURCE,mode='node_connect')
    assert result['selectedMechanic'] == 'node_connect'
    assert 'override' in result['reason']
    with pytest.raises(ValueError,match='INELIGIBLE_FORCED_MECHANIC'):
        select(nodes.SOURCE,mode='resource_balance')
    with pytest.raises(ValueError,match='MECHANIC_MODE_ERROR'):
        select(nodes.SOURCE,mode='boss')


def test_diversity_only_breaks_exact_fit_ties_after_repetition():
    assert select(AMBIGUOUS,history=['resource_balance'])['status'] == 'AMBIGUOUS_MECHANIC_SELECTION'
    assert select(AMBIGUOUS,history=['resource_balance']*2)['selectedMechanic'] == 'machine_configuration'
    assert select(AMBIGUOUS,history=['machine_configuration']*2)['selectedMechanic'] == 'resource_balance'
    assert select(resources.SOURCE,history=['resource_balance']*2)['selectedMechanic'] == 'resource_balance'
    assert select(AMBIGUOUS,replace(OBJECTIVE,intent='configure'),history=['machine_configuration']*2)['status'] == 'AMBIGUOUS_MECHANIC_SELECTION'


def test_score_formula_is_stable_and_bounded():
    source='La entrada recibe los datos originales. La salida produce las predicciones finales.'
    result=select(source)
    candidate=result['candidates'][0]
    assert candidate['score'] == .8333  # .55 + .25 + .1 * 2/6
    assert all(0 <= c['score'] <= 1 for c in result['candidates'])


def test_seeded_order_repetition_and_topic_padding_do_not_change_selection():
    rng=random.Random(20260915)
    lines=resources.SOURCE.splitlines()
    expected=select(resources.SOURCE)['selectedMechanic']
    for _ in range(100):
        rng.shuffle(lines)
        source='\n'.join(lines + rng.choices(lines,k=3)+['Componentes, parámetros, modos, recursos y dependencias.'])
        result=select(source)
        assert result['selectedMechanic'] == expected
        assert result == select(source)
        assert result['features']['relationCount'] == select(resources.SOURCE)['features']['relationCount']


def test_bounds_reject_before_large_analysis():
    with pytest.raises(ValueError,match='SOURCE_BOUNDS_ERROR'):
        build_structure_graph('x'*60001)
    with pytest.raises(ValueError,match='SOURCE_BOUNDS_ERROR'):
        build_structure_graph('\n'.join(f'El nodo {i} requiere el destino {i+1}.' for i in range(513)))
    with pytest.raises(ValueError,match='OBJECTIVE_ERROR'):
        LearningObjective('x','text',intent='invent')


MATERIALS=json.loads((Path(__file__).parent/'fixtures/mechanic_selector/academic_excerpts.json').read_text())

@pytest.mark.parametrize('material', MATERIALS, ids=lambda m:m['id'])
def test_real_academic_excerpt_results_are_preserved(material):
    result=select(material['source'])
    assert result['status'] == material['expectedStatus']
    assert result['selectedMechanic'] == material['expectedMechanic']
    stored=json.loads((Path(__file__).parent/'fixtures/mechanic_selector/academic_results.json').read_text())
    assert stored[material['id']] == result


def test_quantitative_evidence_cannot_be_borrowed_from_unrelated_relation():
    source=('La carga requiere capacidad ilimitada. Los recursos requieren un ejecutor. '
            'El poeta utiliza dos figuras literarias.')
    assert eligibility(source,'resource_balance')['status']=='SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE'
    result=select(resources.SOURCE)
    candidate=next(c for c in result['candidates'] if c['archetype']=='resource_balance')
    assert len(candidate['evidenceRelationIds'])==candidate['relationshipCount']
    assert result['features']['quantifiedCapacityCount']==1


def test_offline_material_tool_writes_evidence_without_source_text(tmp_path):
    from mindcrafted.generator.mechanic_tools import main
    source=tmp_path/'material.txt'; output=tmp_path/'evidence.json'
    source.write_text(resources.SOURCE)
    result=main([str(source),'--objective','Understand allocation','--output',str(output)])
    saved=json.loads(output.read_text())
    assert saved==result and result['selectedMechanic']=='resource_balance'
    assert 'La carga total asignada' not in output.read_text()
    assert result['sourceLength']==len(resources.SOURCE)
