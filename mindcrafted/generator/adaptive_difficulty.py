"""Offline verification of future variants. Never mutates active worlds or BKT."""
from copy import deepcopy
import hashlib
import json
import subprocess
from .world import world_hash, validate_world
from .world_schema import AdaptiveRegion
from .world_package import quality_gate, CHECKS, ENGINE
from .world_campaign import campaign_hash


def parameters(world):
    if world.get('bosses') or len(world['puzzles']) != 1:
        raise ValueError('ADAPTATION_BOUNDARY_REQUIRES_SINGLE_PRACTICE_REGION')
    p = world['puzzles'][0]; m = p['mechanics']; kind = p['archetype']
    if kind == 'node_connect':
        choices = len(m['edges']); rules = len(m['connectionRules']) + len(m['goals'])
    elif kind == 'resource_balance':
        choices = len(m['loads']) * len(m['targets']); rules = len(m['allocationRules']) + len(m['goals'])
    elif kind == 'machine_configuration':
        choices = sum(len(s['components']) for s in m['slots']) + sum(len(v['values']) for v in m['parameters'])
        rules = len(m['configurationRules']) + len(m['goals'])
    else:
        raise ValueError('UNSUPPORTED_ADAPTIVE_ARCHETYPE')
    return {'choiceCount': choices, 'constraintCount': rules,
            'conceptCombinationCount': len({r['skill'] for r in p['knowledge']['requiredRules']}), 'initialHintLevel': 1}


def verify_catalog(catalog, source):
    AdaptiveRegion.model_validate(catalog)
    c = deepcopy(catalog)
    variants = c['variants']
    if [v['level'] for v in variants] != ['EASY', 'NORMAL', 'HARD']:
        raise ValueError('INVALID_DIFFICULTY_LEVELS')
    signature = None; complexities = []
    for variant in variants:
        w = variant['world']; metrics = parameters(w); p = w['puzzles'][0]
        if p['difficulty']['level'] != {'EASY':'study', 'NORMAL':'normal', 'HARD':'hard'}[variant['level']]:
            raise ValueError('ADAPTATION_DIFFICULTY_MISMATCH')
        binding = (p['id'], p['archetype'], p['objective'], p['knowledge']['concept'],
                   sorted((r['skill'], r['evidence']) for r in p['knowledge']['requiredRules']))
        if p['objective'] != c['objective'] or signature is not None and binding != signature:
            raise ValueError('ADAPTATION_CHANGED_LEARNING_OBJECTIVE')
        signature = binding
        if variant['worldHash'] != world_hash(w) or metrics != variant['parameters']:
            raise ValueError('ADAPTATION_PARAMETER_MISMATCH')
        report = validate_world(w, source)
        if not report['ok']:
            raise ValueError('ADAPTATION_INVALID_WORLD: ' + '; '.join(report['errors']))
        complexities.append(metrics['choiceCount'])
    if not complexities[0] < complexities[1] < complexities[2]:
        raise ValueError('ADAPTATION_REQUIRES_DISTINCT_ORDERED_COMPLEXITY')
    recommend_difficulty({'challengeId':'catalog_validation','objective':c['objective'],
                          'archetype':variants[0]['world']['puzzles'][0]['archetype'], 'base':c['base'],
                          'policy':c.get('policy',{})})
    return c


def attach_variants(package, region_index, worlds, source, *, base='NORMAL', policy=None):
    """Application-owned generation boundary; all three outputs need full gates.

    Worlds may come from existing Agent API/Planner. No provider is called here,
    and no model suggestion can bypass validation. Returns a new development
    package; real publication additionally needs a Judge for every variant.
    """
    if package.get('developmentDemo') is not True:
        raise ValueError('ADAPTIVE_REAL_PUBLICATION_REQUIRES_VARIANT_JUDGES')
    if type(region_index) is not int or not 0 < region_index < len(package['campaign']['regions']):
        raise ValueError('ADAPTATION_REQUIRES_FUTURE_REGION')
    region = package['campaign']['regions'][region_index]
    if hashlib.sha256(source.encode()).hexdigest() != region['sourceHash']:
        raise ValueError('ADAPTATION_SOURCE_MISMATCH')
    objective = region['world']['puzzles'][0]['objective']
    catalog = {'policyVersion': 1, 'objective': objective, 'base': base, 'policy':policy or {}, 'variants': [
        {'level': level, 'world': deepcopy(worlds[level]), 'worldHash': world_hash(worlds[level]),
         'parameters': parameters(worlds[level])} for level in ('EASY','NORMAL','HARD')]}
    catalog = verify_catalog(catalog, source)
    if package.get('campaignPlan'):
        from .campaign_plan import validate_realization
        plan = package['campaignPlan']
        pid = region['world']['puzzles'][0]['id']
        planned = next((r for r in plan['regions'] if any(q['puzzleId']==pid for q in r['quests'])), None)
        if planned is None:
            raise ValueError('ADAPTATION_MISSING_PLANNED_OBJECTIVE')
        for variant in catalog['variants']:
            validate_realization(plan, source, variant['world'], planned['id'])
    if world_hash(worlds[base]) != region['worldHash']:
        raise ValueError('ADAPTATION_BASE_MISMATCH')
    gates = {}
    for variant in catalog['variants']:
        report = quality_gate(variant['world'], source)
        if report['errors'] or not all(report['checks'].get(k) is True for k in CHECKS):
            raise ValueError('ADAPTATION_QUALITY_GATE_FAILED: ' + str(report['errors']))
        gates[variant['level']] = report
    result = deepcopy(package)
    result['campaign']['regions'][region_index]['adaptive'] = catalog
    result.setdefault('adaptiveQuality', {})[region['id']] = gates
    result['config']['worldHash'] = campaign_hash(result['campaign'])
    return result


def recommend_difficulty(context, suggestion=None):
    """Use the exact browser policy for generation; no duplicate Python thresholds."""
    script = "const p=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{let x=JSON.parse(s);console.log(JSON.stringify(x.suggestion===null?p.recommend(x.context):p.verifySuggestion(x.context,x.suggestion)));});"
    r = subprocess.run(['node', '-e', script, str(ENGINE/'world/difficulty-policy.js')],
                       input=json.dumps({'context': context, 'suggestion': suggestion}), text=True,
                       capture_output=True, timeout=5)
    if r.returncode:
        raise ValueError('DIFFICULTY_POLICY_REJECTED: ' + r.stderr[-1500:])
    return json.loads(r.stdout)
