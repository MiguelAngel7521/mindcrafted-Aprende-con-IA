"""Explicit authored fixture, not real academic-source or AI approval evidence."""
from . import node_connect_demo, resource_balance_demo, boss_demo
from .campaign_plan import validate_plan
from .knowledge_features import build_structure_graph, normalized

SOURCE = boss_demo.SOURCE


def practice_blueprints():
    node = node_connect_demo.blueprint()
    node['puzzles'][0]['knowledge']['requiredRules'][0]['evidence'] = node_connect_demo.SOURCE
    return [node, resource_balance_demo.blueprint()]


def plan_fixture():
    graph = build_structure_graph(SOURCE)
    objectives, regions = [], []
    for index, (module, intent, stage) in enumerate([
        (node_connect_demo, 'connect', 'introduce'),
        (resource_balance_demo, 'distribute', 'apply')]):
        puzzle = practice_blueprints()[index]['puzzles'][0]
        relations = [r for r in graph['relations'] if any(normalized(r['evidence']['quote']) in normalized(rule['evidence']) for rule in puzzle['knowledge']['requiredRules'])]
        oid = 'objective_' + str(index)
        objectives.append(dict(id=oid, text=puzzle['objective'],
            concepts=sorted({r[k] for r in relations for k in ('subject','object')}),
            relations=[r['id'] for r in relations],
            evidence=[dict(relationId=r['id'], **r['evidence']) for r in relations],
            prerequisites=[objectives[-1]['id']] if objectives else [],
            expectedMastery=.6+index*.2,difficulty=stage,intent=intent))
        regions.append(dict(id='region_'+str(index), narrativeTitle=module.blueprint()['title'],
            objectives=[oid], prerequisites=[regions[-1]['id']] if regions else [],
            quests=[dict(id='quest_'+str(index), objectiveId=oid,puzzleId=puzzle['id'],
                narrativeProblem=module.blueprint()['introduction'],consequence='open_route',
                mechanic=puzzle['mechanics']['archetype'])]))
    plan = dict(schemaVersion=1,id='archive_curriculum',narrativeTitle='Recuperación del archivo',
        learningObjectives=objectives,regions=regions,difficultyCurve=['introduce','apply'],
        bossPlan=dict(afterRegion=regions[-1]['id'],difficulty='boss',
            phases=[dict(objectiveId=o['id'],mechanic=r['quests'][0]['mechanic']) for o,r in zip(objectives,regions)]))
    return validate_plan(plan,SOURCE).model_dump()
