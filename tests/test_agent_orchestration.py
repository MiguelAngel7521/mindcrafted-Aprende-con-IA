"""Guarded agent contract; only the provider is scripted, never gameplay arbitration."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest

from mindcrafted.generator.agent_tools import AgentSession, Budgets
from mindcrafted.generator.agent_provider import ScriptedProvider, RealProvider, ProviderConfig
from mindcrafted.generator.agent_runner import AgentRunner
from mindcrafted.generator.agent_publication import PublicationAuthority
from mindcrafted.generator.node_connect_demo import SOURCE, blueprint
from mindcrafted.generator.provider_response import ProviderError

JUDGE={'approved':True,'scores':dict(embodiedLearning=25,worldIntegration=25,interactionQuality=25,technicalSolvability=25),'issues':[]}


def script(candidate=None, *, bad=None, judge=None):
    def reply(request):
        if 'tool' not in request:
            return deepcopy(judge or JUDGE)
        tool=request['tool'];args={}
        if tool=='select_mechanic':
            args=dict(objectiveId='learning',text='Connect the software dependencies',
                relationIds=[r['id'] for r in request['knowledgeGraph']['relations']],intent='connect',mode='node_connect')
        if tool in ('design_world','repair_world'):
            args={'objectiveId':'learning','blueprint':deepcopy(bad if tool=='design_world' and bad else candidate or blueprint())}
        if tool in ('design_boss','repair_boss'):
            args={'blueprint':deepcopy(bad if tool=='design_boss' and bad else candidate)}
        return dict(tool=tool,arguments=args,step=request['step'],generationId=request['generationId'])
    return reply


def runner(source=SOURCE, **kwargs):
    session=AgentSession(source,**kwargs)
    return session


def execute(session, responses):
    provider=ScriptedProvider(responses)
    return asyncio.run(AgentRunner(session,provider).run()),provider


@pytest.mark.parametrize('tool',['compile_world','solve_world','run_quality_gate','judge_candidate','package_campaign'])
def test_invalid_state_jumps(tool):
    s=runner()
    with pytest.raises(ValueError,match='INVALID_AGENT_TRANSITION'):
        asyncio.run(s.dispatch(tool,{}))
    assert not s._package


@pytest.mark.parametrize('category',['PROVIDER_TIMEOUT','PROVIDER_RATE_LIMIT','PROVIDER_UPSTREAM_ERROR','PROVIDER_CONNECTION_ERROR','PROVIDER_EMPTY_RESPONSE'])
def test_technical_retry_is_identical_and_never_repair(category):
    s=runner(budgets=Budgets(max_provider_retries=1))
    p=ScriptedProvider([ProviderError(category,'private-secret',retryable=True), {'ok':True}])
    a=AgentRunner(s,p)
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
    assert asyncio.run(a._request({'same':'request'},schema,'test'))=={'ok':True}
    assert p.calls[0]['request']==p.calls[1]['request'] and s.repairs==0
    assert 'private-secret' not in json.dumps(s.audit)


def test_provider_exhaustion_is_not_semantic_repair():
    s=runner(budgets=Budgets(max_provider_retries=0))
    with pytest.raises(ProviderError):execute(s,[ProviderError('PROVIDER_RATE_LIMIT','429',retryable=True)])
    assert s.state=='REJECTED' and s.repairs==0 and not s._package


@pytest.mark.parametrize('budget,expected',[(Budgets(max_tool_calls=1),'TOOL_BUDGET_EXHAUSTED'),
    (Budgets(max_output_bytes=5),'OUTPUT_SIZE_EXCEEDED')])
def test_budgets_fail_closed(budget,expected):
    s=runner(budgets=budget)
    with pytest.raises(ValueError,match=expected):execute(s,[script()]*15)
    assert s.state=='REJECTED' and not s._package


def test_timeout_and_total_execution():
    async def slow(_):await asyncio.sleep(.1);return {}
    s=runner(budgets=Budgets(provider_timeout=.01,max_provider_retries=0))
    with pytest.raises(ProviderError,match='PROVIDER_TIMEOUT'):
        execute(s,[slow])
    s=runner(budgets=Budgets(total_timeout=.01));s._started-=1
    with pytest.raises(ValueError,match='TOTAL_EXECUTION_EXHAUSTED'):execute(s,[script()])


def test_repair_budget_rejects_without_package():
    bad=blueprint();bad['puzzles'][0]['knowledge']['requiredRules'][0]['evidence']='Invented academic evidence not present in the source material.'
    s=runner(budgets=Budgets(max_repairs=1))
    with pytest.raises(ValueError,match='REPAIR_BUDGET_EXHAUSTED'):
        execute(s,[script(candidate=bad)]*15)
    assert s.repairs==1 and s.state=='REJECTED' and not s._world


def test_schema_invalid_repair_replaces_current_candidate():
    from test_agent_tools import prepared,call
    s=prepared();call(s,'design_world',{'objectiveId':'dependencies','blueprint':blueprint()})
    with pytest.raises(ValueError):call(s,'design_world',{'objectiveId':'dependencies','blueprint':{'code':'eval()'}})
    assert s._candidate is None and s.state=='REPAIR_REQUIRED'
    with pytest.raises(ValueError):call(s,'compile_world',{})


@pytest.mark.parametrize('fault',['grounding','eligibility','solver'])
def test_perfect_judge_cannot_override_invalid_candidate(fault):
    bad=blueprint()
    if fault=='grounding':bad['puzzles'][0]['knowledge']['requiredRules'][0]['evidence']='Invented academic evidence not present in the source material.'
    elif fault=='eligibility':
        from mindcrafted.generator.resource_balance_demo import blueprint as resource
        bad=resource()
    else:bad['puzzles'][0]['mechanics']['goals'][0].update(source='DB',target='UI')
    s=runner(budgets=Budgets(max_repairs=0));p=ScriptedProvider([script(candidate=bad)]*15)
    with pytest.raises(ValueError):asyncio.run(AgentRunner(s,p).run())
    assert not any(c['step']=='world_judge' for c in p.calls)
    assert not s._package


def test_real_adapter_reuses_configured_api(monkeypatch):
    from mindcrafted.generator import api
    seen={}
    async def fake(prompt,system,**kwargs):seen.update(kwargs);return '{}'
    monkeypatch.setattr(api,'generate',fake)
    p=RealProvider(ProviderConfig('custom','fixed-model',base_url='https://example.test/v1'))
    asyncio.run(p.respond({}, {'type':'object','properties':{},'additionalProperties':False},step='test',generation_id='g',repair_count=1))
    assert seen['provider']=='custom' and seen['model']=='fixed-model'
    assert seen['max_retries']==1 and seen['fixed_model'] and seen['structured_mode']=='strict'


def test_e2e_repair_gate_test_judge_package_and_browser(tmp_path):
    before=hashlib.sha256(Path('courses.json').read_bytes()).hexdigest()
    bad=blueprint();bad['puzzles'][0]['knowledge']['requiredRules'][0]['evidence']='Invented academic evidence not present in the source material.'
    s=runner();package,p=execute(s,[script(bad=bad)]*20)
    assert s.repairs==1 and s.state=='PACKAGED'
    assert package['developmentDemo'] and not package['quality']['approved']
    assert package['quality']['judgeAuthority']=='TEST_ONLY_JUDGE'
    assert package['quality']['checks']['e2e']
    assert any(c['request'].get('diagnostic') for c in p.calls if c['request'].get('tool')=='repair_world')
    path=asyncio.run(PublicationAuthority(tmp_path/'published').publish(s))
    assert Path(path).exists()
    stored=json.loads((tmp_path/'published/game.pkg.json').read_text())
    assert not stored['quality']['approved']
    assert hashlib.sha256(Path('courses.json').read_bytes()).hexdigest()==before


def test_boss_cross_phase_invalid_is_rejected_by_agent():
    from mindcrafted.generator.boss_demo import SOURCE as material,blueprint as boss_blueprint
    from test_boss_campaign import packages
    from mindcrafted.generator.pillar_demo import SOURCE as lesson_source
    lesson,_=packages();bad=boss_blueprint()
    bad['sharedState'][0]['values']=[1,4]
    bad['phases'][0]['exports'][0]['cases'][1]['value']=1
    s=runner(material,previous_lessons=[(lesson,lesson_source)],budgets=Budgets(max_repairs=0))
    p=ScriptedProvider([script(candidate=bad)]*10)
    with pytest.raises(ValueError,match='REPAIR_BUDGET_EXHAUSTED'):
        asyncio.run(AgentRunner(s,p).run(boss=True))
    assert any(e.get('errorCategory')=='BOSS_CROSS_PHASE_UNSOLVABLE' for e in s.audit)
    assert not s._package and not any(c['step']=='world_judge' for c in p.calls)


@pytest.fixture(scope='module')
def approved_test_session():
    s=runner()
    execute(s,[script()]*20)
    return s


@pytest.mark.parametrize('check',['solver','educational','mechanicEligibility','e2e','boss'])
def test_publication_authority_vetoes_perfect_judge_on_any_deterministic_failure(approved_test_session,tmp_path,check):
    s=deepcopy(approved_test_session)
    s._gate['checks'][check]=False
    with pytest.raises(ValueError,match='PUBLICATION_REJECTED'):
        asyncio.run(PublicationAuthority(tmp_path/'result').publish(s))
    assert not (tmp_path/'result').exists()


def test_judge_rejection_after_real_deterministic_pass(approved_test_session):
    s=deepcopy(approved_test_session);s.state='GATED';s._package=None
    rejected=dict(JUDGE,approved=False,issues=['Educational mismatch'])
    AgentRunner(s,ScriptedProvider([rejected]))
    with pytest.raises(ValueError,match='AI_JUDGE_REJECTION'):
        asyncio.run(s.dispatch('judge_candidate',{}))
    assert s.state=='REPAIR_REQUIRED' and s._gate is None
    with pytest.raises(ValueError,match='INVALID_AGENT_TRANSITION'):
        asyncio.run(s.dispatch('package_campaign',{}))


def test_changed_package_and_existing_destination_are_never_written(approved_test_session,tmp_path):
    s=deepcopy(approved_test_session);s._package['world']['title']='changed'
    with pytest.raises(ValueError,match='PUBLICATION_REJECTED'):
        asyncio.run(PublicationAuthority(tmp_path/'result').publish(s))
    s=deepcopy(approved_test_session)
    with pytest.raises(ValueError,match='DESTINATION_EXISTS'):
        asyncio.run(PublicationAuthority(tmp_path).publish(s))


def test_cannot_reset_repair_budget_via_analyze_or_reselection():
    from test_agent_tools import prepared,call
    s=prepared()
    with pytest.raises(ValueError):call(s,'design_world',{'objectiveId':'dependencies','blueprint':{}})
    for tool in ('analyze_material','select_mechanic','design_world'):
        with pytest.raises(ValueError,match='INVALID_AGENT_TRANSITION'):call(s,tool,{})
    assert s.state=='REPAIR_REQUIRED'


@pytest.mark.parametrize('field,value',[('step',999),('generationId','other'),('tool','openDoor'),('arguments',{'approved':True})])
def test_envelope_validation_before_dispatch(field,value):
    s=runner(budgets=Budgets(max_repairs=0))
    def invalid(request):
        response=script()(request);response[field]=value;return response
    with pytest.raises(ValueError):execute(s,[invalid]*4)
    assert s._graph is None and not any(e['tool']=='analyze_material' for e in s.audit)


def test_permission_categories_and_closed_schemas():
    from mindcrafted.generator.agent_tools import tool_registry
    registry=tool_registry()
    assert {t['permission'] for t in registry}=={'ANALYZE','PLAN','DESIGN','VALIDATE','COMPILE','SOLVE','REVIEW','REPAIR','PACKAGE'}
    assert all(t['parameters']['additionalProperties'] is False for t in registry)


def test_worker_deadline_is_terminal():
    from test_agent_tools import prepared,call
    s=prepared();call(s,'design_world',{'objectiveId':'dependencies','blueprint':blueprint()})
    s.budgets=Budgets(tool_timeout=.00001)
    with pytest.raises(TimeoutError):call(s,'compile_world',{})
    assert s.state=='REJECTED' and not s._package


def test_boss_prerequisites_cannot_be_invented():
    from mindcrafted.generator.boss_demo import SOURCE as material,blueprint as boss_blueprint
    s=runner(material,budgets=Budgets(max_repairs=0))
    p=ScriptedProvider([script(candidate=boss_blueprint())]*10)
    with pytest.raises(ValueError):asyncio.run(AgentRunner(s,p).run(boss=True))
    assert any(e.get('errorCategory')=='BOSS_CONCEPT_NOT_PREVIOUSLY_INTRODUCED' for e in s.audit)


def test_boss_e2e_repair_then_real_campaign_package(tmp_path):
    from mindcrafted.generator.boss_demo import SOURCE as material,blueprint as boss_blueprint
    from test_boss_campaign import packages
    from mindcrafted.generator.pillar_demo import SOURCE as lesson_source
    lesson,_=packages();good=boss_blueprint();bad=deepcopy(good)
    bad['sharedState'][0]['values']=[1,4];bad['phases'][0]['exports'][0]['cases'][1]['value']=1
    s=runner(material,previous_lessons=[(lesson,lesson_source)],budgets=Budgets(tool_timeout=240))
    p=ScriptedProvider([script(candidate=good,bad=bad)]*20)
    result=asyncio.run(AgentRunner(s,p).run(boss=True))
    assert s.repairs==1 and len(result['campaign']['regions'])==2
    assert result['regionQuality'][-1]['checks']['boss']
    assert result['regionQuality'][-1]['checks']['e2e']
    path=asyncio.run(PublicationAuthority(tmp_path/'campaign').publish(s))
    assert Path(path).exists()
    manifest=json.loads((tmp_path/'campaign/campaign.json').read_text())
    assert manifest['checks']['ok'] and manifest['checks']['regions']==2
    assert manifest['developmentDemo']


def test_all_wire_commands_derive_valid_strict_schema():
    from jsonschema import Draft202012Validator
    from mindcrafted.generator.agent_tools import TOOLS
    from mindcrafted.generator.agent_runner import command_schema
    from mindcrafted.generator.structured_schema import strict_response_schema
    for tool in TOOLS:
        schema=strict_response_schema(command_schema(tool,'generation',1))
        Draft202012Validator.check_schema(schema)
        assert schema['additionalProperties'] is False


@pytest.mark.parametrize('kwargs',[{'max_repairs':-1},{'max_provider_retries':11},
    {'max_tool_calls':0},{'provider_timeout':float('inf')},{'total_timeout':0},{'max_output_bytes':0}])
def test_invalid_budget_configuration(kwargs):
    with pytest.raises(ValueError,match='INVALID_BUDGET'):Budgets(**kwargs)


def test_non_transient_provider_error_never_retries():
    s=runner();p=ScriptedProvider([ProviderError('PROVIDER_HTTP_ERROR','HTTP 401')])
    with pytest.raises(ProviderError):asyncio.run(AgentRunner(s,p).run())
    assert len(p.calls)==1 and s.repairs==0


def test_actual_empty_response_is_retried_without_repair():
    s=runner();p=ScriptedProvider(['',{'ok':True}]);a=AgentRunner(s,p)
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
    assert asyncio.run(a._request({},schema,'test'))=={'ok':True}
    assert len(p.calls)==2 and s.repairs==0


def test_schema_failure_not_transport_retry():
    s=runner();p=ScriptedProvider(['not JSON']);a=AgentRunner(s,p)
    with pytest.raises(ValueError):asyncio.run(a._request({}, {'type':'object'},'test'))
    assert len(p.calls)==1


def test_application_authority_required_before_any_write(tmp_path):
    s=runner()
    with pytest.raises(ValueError,match='INVALID_AGENT_TRANSITION'):
        asyncio.run(PublicationAuthority(tmp_path/'forbidden').publish(s))
    assert not (tmp_path/'forbidden').exists()


def test_review_tool_deadline_cancels_slow_provider(approved_test_session):
    s=deepcopy(approved_test_session);s.state='GATED';s._package=None
    s.budgets=Budgets(tool_timeout=.01)
    async def slow_review(world,gate):
        await asyncio.sleep(10)
        return JUDGE
    s._review=slow_review
    with pytest.raises(TimeoutError):asyncio.run(s.dispatch('judge_candidate',{}))
    assert s.state=='REJECTED' and s._gate is None
    assert s.audit[-1]['errorCategory']=='TOOL_TIMEOUT'
