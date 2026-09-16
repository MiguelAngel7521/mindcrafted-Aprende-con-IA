"""Bounded composition of existing archetypes. No new puzzle arbitration engine."""
from copy import deepcopy
from itertools import product
import json

from . import finite_puzzle, node_connect, resource_balance, machine_configuration
from .knowledge_features import build_structure_graph, objective_from_evidence, normalized
from .mechanic_selector import MechanicSelector
from .world_schema import BossBlueprint, BossSpec
from .world_solver import solve_puzzle

MAX_VARIANTS = 16
MAX_EVALUATED_STATES = 32768
MODULES = {'node_connect': node_connect, 'resource_balance': resource_balance,
           'machine_configuration': machine_configuration}


def _key(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _index(items, label):
    return finite_puzzle.index(items, label)


def _binding_target(mechanics, binding):
    if binding['kind'] == 'resource_capacity' and mechanics['archetype'] == 'resource_balance':
        for rule in mechanics['allocationRules']:
            if rule['kind'] == 'capacity' and rule['ruleId'] == binding['ruleId']:
                target = next((v for v in rule['limits'] if v['target'] == binding['targetId']), None)
                if target is not None:
                    return target
    if binding['kind'] == 'machine_capacity' and mechanics['archetype'] == 'machine_configuration' and binding['targetId'] is None:
        target = next((r for r in mechanics['configurationRules'] if r['kind'] == 'capacity' and r['ruleId'] == binding['ruleId']), None)
        if target is not None:
            return target
    raise ValueError('BOSS_REFERENCE_ERROR: invalid capacity binding')


def effective_puzzle(puzzle, phase, shared):
    result = deepcopy(puzzle)
    for binding in phase['bindings']:
        if binding['variable'] not in shared:
            raise ValueError('BOSS_SHARED_STATE_ERROR: input unavailable')
        _binding_target(result['mechanics'], binding)['max'] = shared[binding['variable']]
    return result


def phase_outputs(phase, state, shared):
    result = dict(shared)
    for output in phase['exports']:
        value = output['controlId'] in state if output['kind'] == 'edge_present' else state[output['controlId']]
        case = next((c for c in output['cases'] if type(c['when']) is type(value) and c['when'] == value), None)
        if case is None:
            raise ValueError('BOSS_SHARED_STATE_ERROR: winning state has no output case')
        result[output['variable']] = case['value']
    return result


def validate_contract(boss, puzzles, source, prior_skills):
    BossSpec.model_validate(boss)
    phases = _index(boss['phases'], 'boss phases')
    variables = _index(boss['sharedState'], 'boss variables')
    _index([{'id':boss['id']}, {'id':boss['completion']['flag']}], 'boss IDs')
    if len(set(p['puzzleId'] for p in phases.values())) != len(phases):
        raise ValueError('BOSS_REFERENCE_ERROR: repeated phase puzzle')
    required = {r['skill'] for p in phases.values() for r in puzzles.get(p['puzzleId'], {}).get('knowledge', {}).get('requiredRules', [])}
    if set(boss['requiredSkills']) != required or len(boss['requiredSkills']) != len(required):
        raise ValueError('BOSS_REFERENCE_ERROR: required skills must match phase rules')
    if not required <= set(prior_skills):
        raise ValueError('BOSS_CONCEPT_NOT_PREVIOUSLY_INTRODUCED: ' + ', '.join(sorted(required-set(prior_skills))))
    if any(len(set(v['values'])) != len(v['values']) for v in variables.values()):
        raise ValueError('BOSS_SHARED_STATE_ERROR: duplicate domain values')
    producers, used, concepts, archetypes, selections = {}, set(), set(), set(), {}
    graph = build_structure_graph(source)
    for i, phase in enumerate(boss['phases']):
        if phase['next'] != (boss['phases'][i+1]['id'] if i+1 < len(phases) else None):
            raise ValueError('BOSS_TRANSITION_ERROR: phases must form one forward terminating chain')
        puzzle = puzzles.get(phase['puzzleId'])
        if not puzzle or puzzle['mechanics']['archetype'] not in MODULES:
            raise ValueError('BOSS_REFERENCE_ERROR: missing puzzle or unsupported archetype')
        mechanics = puzzle['mechanics']; archetype = mechanics['archetype']
        concepts.add(puzzle['knowledge']['concept']); archetypes.add(archetype)
        rules = _index(puzzle['knowledge']['requiredRules'], 'phase rules')
        objective = objective_from_evidence(graph, puzzle['objective'], [r['evidence'] for r in rules.values()], objective_id=phase['id'])
        selections[phase['id']] = MechanicSelector().select(graph, source, objective, mode=archetype)
        paths = set()
        for binding in phase['bindings']:
            if binding['variable'] not in producers:
                raise ValueError('BOSS_SHARED_STATE_ERROR: input must have an earlier producer')
            path = (binding['kind'],binding['ruleId'],binding['targetId'])
            if path in paths:
                raise ValueError('BOSS_SHARED_STATE_ERROR: conflicting writes')
            paths.add(path); used.add(binding['variable'])
            _binding_target(mechanics, binding)
        for output in phase['exports']:
            variable = output['variable']
            if variable not in variables or variable in producers:
                raise ValueError('BOSS_SHARED_STATE_ERROR: unknown or repeated producer')
            producers[variable] = phase['id']
            if output['kind'] == 'edge_present' and archetype == 'node_connect':
                if output['controlId'] not in {e['id'] for e in mechanics['edges']}:
                    raise ValueError('BOSS_REFERENCE_ERROR: unknown edge output')
                choices = [False, True]
            elif output['kind'] == 'configuration_value' and archetype in ('resource_balance','machine_configuration'):
                choices = MODULES[archetype].domains(mechanics).get(output['controlId'])
                if choices is None:
                    raise ValueError('BOSS_REFERENCE_ERROR: unknown control output')
            else:
                raise ValueError('BOSS_REFERENCE_ERROR: incompatible output probe')
            seen = set()
            for case in output['cases']:
                key = _key(case['when'])
                if key in seen or not any(type(case['when']) is type(v) and case['when'] == v for v in choices) or case['value'] not in variables[variable]['values']:
                    raise ValueError('BOSS_SHARED_STATE_ERROR: invalid output cases')
                seen.add(key)
        for relation in phase['bindings'] + phase['exports']:
            if relation['ruleId'] not in rules or normalized(relation['evidence']) not in normalized(source):
                raise ValueError('BOSS_GROUNDING_ERROR: binding must cite source and an educational rule')
    if set(variables) != set(producers) or used != set(variables):
        raise ValueError('BOSS_SHARED_STATE_ERROR: every variable needs a producer and later consumer')
    if not 2 <= len(archetypes) <= 4 or set(boss['requiredConcepts']) != concepts or len(boss['requiredConcepts']) != len(concepts):
        raise ValueError('BOSS_CONCEPT_ERROR: combine distinct taught concepts and at least two archetypes')
    return selections


def _states(puzzle):
    m = puzzle['mechanics']
    if m['archetype'] == 'node_connect':
        return ([e['id'] for e, on in zip(m['edges'], mask) if on]
                for mask in product((False,True), repeat=len(m['edges'])))
    domains = MODULES[m['archetype']].domains(m)
    return (dict(zip(domains, values)) for values in product(*domains.values()))


def _actions(puzzle, state):
    m = puzzle['mechanics']
    if m['archetype'] == 'node_connect':
        edges = {e['id']:e for e in m['edges']}
        actions = [{'type':'control','controlId':edges[e][k]} for e in state for k in ('source','target')]
    else:
        domains = MODULES[m['archetype']].domains(m)
        actions = [{'type':'control','controlId':k} for k,v in state.items() for _ in range(domains[k].index(v))]
    return actions + [{'type':'submit'}]


def solve_boss(boss, puzzles, source, prior_skills):
    selections = validate_contract(boss,puzzles,source,prior_skills)
    contexts = {_key({}): {'shared':{}, 'route':[]}}
    proofs, causal, total = [], {}, 0
    for phase in boss['phases']:
        following = {}
        for context in contexts.values():
            shared = context['shared']
            puzzle = effective_puzzle(puzzles[phase['puzzleId']], phase, shared)
            try:
                proof = solve_puzzle(puzzle)
            except ValueError as error:
                raise ValueError(f"BOSS_CROSS_PHASE_UNSOLVABLE: {phase['id']} {shared}: {error}") from error
            total += proof['evaluatedStates']
            if total > MAX_EVALUATED_STATES:
                raise ValueError('BOSS_SOLUTION_BOUNDS: state budget exceeded')
            module = MODULES[puzzle['mechanics']['archetype']]
            winning = [s for s in _states(puzzle) if module.simulate(puzzle['mechanics'], s)['ok']]
            signatures = frozenset(_key(s) for s in winning)
            for binding in phase['bindings']:
                variable = binding['variable']
                others = {b['variable']:shared[b['variable']] for b in phase['bindings'] if b['variable'] != variable}
                causal.setdefault((phase['id'],variable),{}).setdefault(_key(others),{})[shared[variable]] = signatures
            proofs.append({'phaseId':phase['id'],'shared':shared,'solutionCount':len(winning),'evaluatedStates':proof['evaluatedStates']})
            for state in winning:
                output = phase_outputs(phase,state,shared)
                actions = _actions(puzzle,state)
                solution = dict(proof, actions=actions, steps=len(actions))
                solution['solutionEdges' if puzzle['mechanics']['archetype']=='node_connect' else 'solution'] = state
                route = context['route'] + [{'phaseId':phase['id'],'puzzleId':phase['puzzleId'],
                                             'sharedBefore':shared,'sharedAfter':output,'solution':solution}]
                key = _key(output)
                if key not in following or sum(v['solution']['steps'] for v in route) < sum(v['solution']['steps'] for v in following[key]['route']):
                    following[key] = {'shared':output,'route':route}
                if len(following) > MAX_VARIANTS:
                    raise ValueError('BOSS_SOLUTION_BOUNDS: too many reachable shared states')
        contexts = following
    witnesses = []
    for (phase_id,variable),groups in causal.items():
        witness = None
        for variants in groups.values():
            for a, first in variants.items():
                for b, second in variants.items():
                    if first != second:
                        witness = {'phaseId':phase_id,'variable':variable,'values':[a,b],
                                   'state':json.loads(sorted(first ^ second)[0])}
                        break
                if witness: break
            if witness: break
        if witness is None:
            raise ValueError('BOSS_DECORATIVE_SHARED_STATE: ' + variable)
        witnesses.append(witness)
    best = min(contexts.values(),key=lambda c:sum(r['solution']['steps'] for r in c['route']))
    return {'ok':True,'recoverable':True,'route':best['route'],'variantProofs':proofs,
            'causalityWitnesses':witnesses,'evaluatedStates':total,'reachableFinalStates':len(contexts),
            'mechanicSelection':selections,'failurePolicy':boss['failurePolicy']}


def compile_boss(blueprint, source, *, prior_skills=(), world_id='boss_world'):
    BossBlueprint.model_validate(blueprint)
    from .world import compile_world
    spec = {k:deepcopy(v) for k,v in blueprint.items() if k not in ('introduction','phases')}
    spec['phases'] = [{**{k:deepcopy(v) for k,v in phase.items() if k!='puzzle'}, 'puzzleId':phase['puzzle']['id']} for phase in blueprint['phases']]
    puzzles = _index([phase['puzzle'] for phase in blueprint['phases']], 'boss puzzles')
    solve_boss(spec,puzzles,source,prior_skills)
    return compile_world({'title':blueprint['title'],'introduction':blueprint['introduction'],'puzzles':list(puzzles.values())},
                         source,world_id,difficulty='hard',prior_skills=prior_skills,boss=spec)


def validate_boss_world(world,source):
    if not world.get('bosses'):
        return {}
    if len(world['bosses']) != 1:
        raise ValueError('BOSS_REFERENCE_ERROR: one encounter per world')
    boss = world['bosses'][0]
    puzzles = _index(world['puzzles'],'boss world puzzles')
    ids = [p['puzzleId'] for p in boss['phases']]
    if ids != list(puzzles):
        raise ValueError('BOSS_TRANSITION_ERROR: encounter must follow world puzzle order')
    for i,pid in enumerate(ids):
        if puzzles[pid]['prerequisites'] != ids[:i]:
            raise ValueError('BOSS_TRANSITION_ERROR: prerequisites do not match phases')
        if puzzles[pid]['failure']['autoReset'] != (boss['failurePolicy']=='checkpoint'):
            raise ValueError('BOSS_RECOVERY_ERROR: reset policy mismatch')
    final = puzzles[ids[-1]]
    flag = boss['completion']['flag']
    if flag not in final['success']['setFlags'] or any(flag in puzzles[pid]['success']['setFlags'] for pid in ids[:-1]):
        raise ValueError('BOSS_WORLD_CONSEQUENCE_ERROR: completion must belong to final phase')
    if final['success']['xp'] != 75 + boss['completion']['xpBonus']:
        raise ValueError('BOSS_REWARD_ERROR: final reward inconsistent')
    return {boss['id']:solve_boss(boss,puzzles,source,world.get('priorSkills',[]))}
