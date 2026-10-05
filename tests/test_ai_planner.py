import asyncio
from copy import deepcopy
import json
from pathlib import Path
import hashlib
import pytest
from mindcrafted.generator.campaign_plan import CampaignPlan, validate_plan, validate_realization
from mindcrafted.generator.planner_demo import SOURCE, plan_fixture, practice_blueprints
from mindcrafted.generator.boss_demo import blueprint as boss_blueprint
from mindcrafted.generator.agent_tools import AgentSession, Budgets
from mindcrafted.generator.agent_runner import AgentRunner
from mindcrafted.generator.agent_provider import ScriptedProvider
from mindcrafted.generator.ai_planner import CampaignPlanner
from mindcrafted.generator.agent_publication import PublicationAuthority

JUDGE = {'approved':True,'scores':dict(embodiedLearning=25,worldIntegration=25,interactionQuality=25,technicalSolvability=25),'issues':[]}


def response(bad=None, always_bad=False):
    def reply(req):
        if 'tool' not in req: return JUDGE
        tool = req['tool']; args = {}
        if tool in ('plan_campaign','repair_plan'):
            args = {'plan':deepcopy(bad if bad and (tool=='plan_campaign' or always_bad) else plan_fixture())}
        elif tool == 'select_mechanic':
            plan = req['planBinding']['plan']; rid = req['planBinding']['regionId']
            region = next(r for r in plan['regions'] if r['id']==rid)
            obj = next(o for o in plan['learningObjectives'] if o['id']==region['objectives'][0])
            args = dict(objectiveId=obj['id'],text=obj['text'],relationIds=obj['relations'],intent=obj['intent'],mode=region['quests'][0]['mechanic'])
        elif tool in ('design_world','repair_world'):
            index = int(req['planBinding']['regionId'].split('_')[-1])
            args = dict(objectiveId='objective_'+str(index),blueprint=practice_blueprints()[index])
        elif tool in ('design_boss','repair_boss'): args = {'blueprint':boss_blueprint()}
        return dict(tool=tool,arguments=args,step=req['step'],generationId=req['generationId'])
    return reply


def test_fixture_schema_and_grounding():
    from jsonschema import Draft202012Validator
    from mindcrafted.generator.structured_schema import strict_response_schema
    plan = plan_fixture()
    Draft202012Validator(strict_response_schema(CampaignPlan.model_json_schema())).validate(plan)
    assert validate_plan(plan,SOURCE).model_dump()==plan
    assert len({q['mechanic'] for r in plan['regions'] for q in r['quests']})==2


@pytest.mark.parametrize('fault,category',[
    ('concept','UNGROUNDED_CONCEPT'),('evidence','SOURCE_EVIDENCE_ERROR'),
    ('relation','SOURCE_EVIDENCE_ERROR'),('cycle','CYCLIC_PREREQUISITES'),
    ('missing','MISSING_PREREQUISITE'),('mechanic','INELIGIBLE_OR_LOWER_FIT_MECHANIC'),
    ('omit','UNREACHABLE_LEARNING_OBJECTIVE'),('boss','BOSS_SKILL_NOT_TAUGHT'),
    ('regions','too_long'),('unreachable','UNREACHABLE_REGION'),
    ('code','EXECUTABLE_PLAN_CONTENT'),('extra','extra_forbidden'),
    ('quest','QUEST_OBJECTIVE_MISMATCH'),('difficulty','INVALID_DIFFICULTY_CURVE')])
def test_invalid_plans(fault,category):
    p=plan_fixture();o=p['learningObjectives'][0]
    if fault=='concept':o['concepts'][0]='invented'
    elif fault=='evidence':o['evidence'][0]['quote']='An invented academic statement.'
    elif fault=='relation':o['relations'][0]='invented'
    elif fault=='cycle':o['prerequisites']=['objective_1']
    elif fault=='missing':o['prerequisites']=['missing']
    elif fault=='mechanic':p['regions'][0]['quests'][0]['mechanic']='resource_balance'
    elif fault=='omit':p['regions'].pop();p['bossPlan']['afterRegion']='region_0'
    elif fault=='boss':p['bossPlan']['phases'][0]['objectiveId']='unknown'
    elif fault=='regions':p['regions']*=3
    elif fault=='unreachable':p['regions'][1]['prerequisites']=[]
    elif fault=='code':p['narrativeTitle']='openDoor("gate")'
    elif fault=='extra':p['callback']='run_game'
    elif fault=='quest':p['regions'][0]['quests'][0]['objectiveId']='objective_1'
    elif fault=='difficulty':p['difficultyCurve'].reverse()
    with pytest.raises(ValueError,match=category):validate_plan(p,SOURCE)


def test_plan_repair_uses_existing_agent_loop():
    bad=plan_fixture();bad['learningObjectives'][0]['prerequisites']=['objective_1']
    s=AgentSession(SOURCE);p=ScriptedProvider([response(bad)]*6)
    result=asyncio.run(AgentRunner(s,p).run(plan_only=True))
    assert result==plan_fixture() and s.repairs==1 and s.state=='PLAN_VALIDATED'
    assert s._package is None
    assert any('CYCLIC_PREREQUISITES' in (c['request'].get('diagnostic') or {}).get('message','') for c in p.calls)
    with pytest.raises(ValueError):asyncio.run(s.dispatch('package_campaign',{}))


def test_bad_plan_exhausts_repairs_without_judge_or_package():
    bad=plan_fixture();bad['regions'][1]['prerequisites']=[]
    s=AgentSession(SOURCE,budgets=Budgets(max_repairs=1))
    p=ScriptedProvider([response(bad,True)]*10)
    with pytest.raises(ValueError,match='REPAIR_BUDGET_EXHAUSTED'):
        asyncio.run(AgentRunner(s,p).run(plan_only=True))
    assert s._plan is None and s._package is None and s.state=='REJECTED'
    assert not any(c['step']=='world_judge' for c in p.calls)


def test_realization_cannot_skip_practice_or_invent_boss_skills():
    p=plan_fixture();candidate=practice_blueprints()[0]
    assert validate_realization(p,SOURCE,candidate,'region_0')
    candidate['puzzles']=[]
    with pytest.raises(ValueError,match='MISSING_PLANNED_PUZZLE'):validate_realization(p,SOURCE,candidate,'region_0')
    with pytest.raises(ValueError,match='BOSS_SKILL_NOT_TAUGHT'):validate_realization(p,SOURCE,boss_blueprint())


def test_campaign_e2e_plan_repair_practice_boss_reload(tmp_path):
    before=hashlib.sha256(Path('courses.json').read_bytes()).hexdigest()
    bad=plan_fixture();bad['regions'][1]['prerequisites']=[]
    provider=ScriptedProvider([response(bad)]*60)
    planner=CampaignPlanner(SOURCE,provider)
    package=asyncio.run(planner.run())
    assert len(package['campaign']['regions'])==3
    assert planner.sessions[0].repairs==1
    assert all(q['checks']['e2e'] for q in package['regionQuality'])
    assert all(q['judgeAuthority']=='TEST_ONLY_JUDGE' and not q['approved'] for q in package['regionQuality'])
    path=asyncio.run(PublicationAuthority(tmp_path/'campaign').publish(planner.final_session))
    manifest=json.loads((Path(path).parent/'campaign.json').read_text())
    assert manifest['checks']['ok'] and manifest['checks']['reload']
    assert manifest['checks']['regions']==3
    assert hashlib.sha256(Path('courses.json').read_bytes()).hexdigest()==before


def test_multiple_objectives_can_share_one_region():
    p=plan_fixture()
    p['regions'][0]['objectives']+=p['regions'][1]['objectives']
    p['regions'][0]['quests']+=p['regions'][1]['quests']
    p['regions'].pop();p['bossPlan']['afterRegion']='region_0'
    validate_plan(p,SOURCE)
    first,second=practice_blueprints();first['puzzles']+=second['puzzles']
    assert validate_realization(p,SOURCE,first,'region_0')


def test_actual_boss_skill_cannot_borrow_unrelated_prior_puzzle():
    from mindcrafted.generator.world import compile_world
    lessons=[({'world':compile_world(bp,SOURCE)},SOURCE) for bp in practice_blueprints()]
    boss=boss_blueprint()
    assert validate_realization(plan_fixture(),SOURCE,boss,previous_lessons=lessons)
    boss['phases'][0]['puzzle']['knowledge']['requiredRules'][0]['skill']='resources.capacity'
    with pytest.raises(ValueError,match='BOSS_SKILL_NOT_TAUGHT'):
        validate_realization(plan_fixture(),SOURCE,boss,previous_lessons=lessons)


def test_required_relations_cannot_be_only_decorative_plan_metadata():
    bp=practice_blueprints()[0]
    bp['puzzles'][0]['knowledge']['requiredRules'][0]['evidence']=bp['puzzles'][0]['knowledge']['requiredRules'][1]['evidence']
    with pytest.raises(ValueError,match='UNPRACTICED_OBJECTIVE_RELATION'):
        validate_realization(plan_fixture(),SOURCE,bp,'region_0')


def test_compiled_quest_and_consequence_match_plan():
    from mindcrafted.generator.world import compile_world
    from mindcrafted.generator.campaign_plan import validate_compiled_plan
    binding={'plan':plan_fixture(),'regionId':'region_0'}
    w=compile_world(practice_blueprints()[0],SOURCE)
    validate_compiled_plan(binding,SOURCE,w)
    w['puzzles'][0]['success']['openEntity']=None
    with pytest.raises(ValueError,match='PLANNED_CONSEQUENCE_MISSING'):validate_compiled_plan(binding,SOURCE,w)


def test_planner_total_budget_is_not_reset_between_regions():
    planner=CampaignPlanner(SOURCE,ScriptedProvider([response()]*10),budgets=Budgets(max_tool_calls=2))
    with pytest.raises(ValueError,match='TOOL_BUDGET_EXHAUSTED'):asyncio.run(planner.run())
    assert planner.final_session is None and all(s.state=='REJECTED' for s in planner.sessions)
    assert len({s._started for s in planner.sessions})==1
