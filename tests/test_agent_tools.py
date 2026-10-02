"""Model arguments cannot extend the tool registry or forge source evidence."""
import asyncio
import json
import pytest
from mindcrafted.generator.agent_tools import AgentSession, tool_registry
from mindcrafted.generator.node_connect_demo import SOURCE


def call(session, tool, arguments):
    return asyncio.run(session.dispatch(tool, arguments))


@pytest.mark.parametrize('tool', ['eval', 'exec', 'openDoor', 'package_campaign', '__class__'])
def test_unregistered_tools_have_no_authority(tool):
    session=AgentSession(SOURCE)
    with pytest.raises(ValueError,match='TOOL_NOT_ALLOWED|INVALID_AGENT_TRANSITION'):
        call(session,tool,{})
    assert session.audit[-1]['result']=='REJECTED'


def test_selection_requires_analysis_and_real_source_references():
    session=AgentSession(SOURCE)
    args=dict(objectiveId='dependencies',text='Connect software dependencies',relationIds=['invented'],intent='connect',mode='AUTO')
    with pytest.raises(ValueError,match='TOOL_PRECONDITION'):
        call(session,'select_mechanic',args)
    graph=call(session,'analyze_material',{})
    with pytest.raises(ValueError,match='REFERENCE_ERROR'):
        call(session,'select_mechanic',args)
    args['relationIds']=[r['id'] for r in graph['relations']]
    result=call(session,'select_mechanic',args)
    assert result['selectedMechanic']=='node_connect'
    assert session.audit[-1]['outputHash']


@pytest.mark.parametrize('extra', ['source','approved','priorSkills','output_dir','expression'])
def test_closed_arguments_reject_injected_authority_without_logging_payload(extra):
    session=AgentSession(SOURCE)
    with pytest.raises(ValueError):
        call(session,'analyze_material',{extra:'private-payload'})
    assert 'private-payload' not in json.dumps(session.audit)


def test_registry_and_results_are_detached():
    registry=tool_registry();registry[0]['name']='openDoor'
    session=AgentSession(SOURCE)
    graph=call(session,'analyze_material',{})
    graph['relations'].clear()
    assert call(session,'analyze_material',{})['relations']
    audit=session.audit;audit.clear()
    assert len(session.audit)==2
    assert tool_registry()[0]['name']=='analyze_material'


def prepared():
    session=AgentSession(SOURCE)
    graph=call(session,'analyze_material',{})
    call(session,'select_mechanic',dict(objectiveId='dependencies',text='Connect software dependencies',
        relationIds=[r['id'] for r in graph['relations']],intent='connect',mode='node_connect'))
    return session


def test_compile_reuses_canonical_solver_and_does_not_publish():
    from mindcrafted.generator.node_connect_demo import blueprint
    session=prepared()
    result=call(session,'design_world',{'objectiveId':'dependencies','blueprint':blueprint()})
    assert result['candidateHash']
    compiled=call(session,'compile_world',{})
    assert compiled['checks']['solver'] and compiled['checks']['educational']
    with pytest.raises(ValueError,match='TOOL_NOT_ALLOWED|INVALID_AGENT_TRANSITION'):
        call(session,'package_campaign',{})


def test_semantically_rejected_replacement_invalidates_previous_candidate():
    from mindcrafted.generator.node_connect_demo import blueprint
    session=prepared()
    call(session,'design_world',{'objectiveId':'dependencies','blueprint':blueprint()})
    invalid=blueprint()
    invalid['puzzles'][0]['knowledge']['requiredRules'][0]['evidence']='This evidence was invented and does not exist in the source.'
    with pytest.raises(ValueError):
        call(session,'design_world',{'objectiveId':'dependencies','blueprint':invalid})
    with pytest.raises(ValueError,match='TOOL_PRECONDITION'):
        call(session,'compile_world',{})
