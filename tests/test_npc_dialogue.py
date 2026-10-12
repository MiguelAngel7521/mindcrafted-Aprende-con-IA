import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import pytest
from mindcrafted.generator.node_connect_demo import SOURCE,blueprint
from mindcrafted.generator.world import compile_world
from mindcrafted.generator.npc_schema import NPCContext,DialogueOutput,NPCProfile
from mindcrafted.generator.npc_dialogue import NPCDialogueAgent,contextual,validate_dialogue
from mindcrafted.generator.agent_provider import ScriptedProvider
from mindcrafted.generator.agent_tools import Budgets
from mindcrafted.generator.provider_response import ProviderError


def node(script, world=None):
    result=subprocess.run(['node','-e',"const assert=require('assert/strict'); const {WorldEngine}=require('./mindcrafted/engine/world/core.js'); const api=require('./mindcrafted/engine/world/npc-context.js'); const w=JSON.parse(require('fs').readFileSync(0,'utf8')); const e=new WorldEngine(w); const p=e.spec.puzzles[0]; "+script],input=json.dumps(world or compile_world(blueprint(),SOURCE)),text=True,capture_output=True,check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


@pytest.fixture
def context():
    return node("console.log(JSON.stringify(e.npcSystem.build(p,'hint')))")


def test_context_is_bounded_scoped_and_read_only(context):
    NPCContext.model_validate(context)
    assert len(json.dumps(context))<24000
    assert 'mechanics' not in context and 'configuration' not in context
    assert all(f['quote'] in SOURCE for f in context['evidence'])
    node("const before=e.snapshot();e.npcSystem.build(p,'hint');assert.deepEqual(e.snapshot(),before);")


def test_canonical_dialogue_contract_export():
    result=subprocess.run(['node','-e',"console.log(JSON.stringify(require('./mindcrafted/engine/world/npc-contract.js')))"],text=True,capture_output=True,check=True)
    assert json.loads(result.stdout)=={'dialogue':DialogueOutput.model_json_schema(),'profile':NPCProfile.model_json_schema()}


@pytest.mark.parametrize('field,value',[
    ('openDoor','gate'),('setFlag','solved'),('giveXP',100),('completeQuest','quest'),
    ('mastery',1.0),('observation',{'correct':True}),('callback','exec()'),
    ('text','Portal → Servicio A → Repositorio → Archivo'),
    ('text','La memoria infinita elimina todos los errores.'),
    ('sourceRefs',['invented']),('hintLevel',4),('text','new Function("giveXP()")'),
    ('text','En la próxima fase asigna Audio a Rápido.'),('text','X'*9000),
])
def test_negative_output_rejected(context,field,value):
    d=contextual(context);d[field]=value
    with pytest.raises(ValueError):validate_dialogue(d,context)


def test_narrative_label_cannot_hide_hallucinated_fact(context):
    c=deepcopy(context);c.update(intent='reaction',maxHintLevel=0,allowedSourceRefs=[],allowedTexts=['Puedes continuar.'])
    answer=contextual(c);answer['text']='La CPU no necesita memoria.'
    with pytest.raises(ValueError,match='UNVERIFIED_WORDING'):validate_dialogue(answer,c)


@pytest.mark.parametrize('failure',['malformed','timeout','oversized','commands','empty'])
def test_provider_failure_falls_back_without_authority(context,failure):
    async def slow(_):await asyncio.sleep(.2);return {}
    value={'malformed':'{','timeout':slow,'oversized':'a'*9000,'commands':{'openDoor':'gate'},'empty':''}[failure]
    agent=NPCDialogueAgent(ScriptedProvider([value]),budgets=Budgets(max_provider_retries=0,provider_timeout=.01,total_timeout=1,max_output_bytes=8000))
    result=asyncio.run(agent.respond(context))
    assert result['fallback'] and result['dialogue']==contextual(context)
    assert agent.audit[-1]['result']=='FALLBACK'


def test_scripted_agent_structured_response_and_technical_retry(context):
    answer=contextual(context);answer['text']=context['allowedTexts'][1]
    provider=ScriptedProvider([ProviderError('PROVIDER_RATE_LIMIT','secret',retryable=True),answer])
    agent=NPCDialogueAgent(provider)
    result=asyncio.run(agent.respond(context))
    assert not result['fallback'] and result['dialogue']==answer
    assert len(provider.calls)==2 and provider.calls[0]['schema']==DialogueOutput.model_json_schema()
    assert provider.calls[0]['request']['permission']=='READ_ONLY_DIALOGUE'
    assert 'secret' not in json.dumps(agent.audit)


def test_hint_policy_levels_and_mastery():
    node("""
const policy=api.hintPolicy;
assert.equal(policy({errors:1,hintsUsed:1},[]),1);
assert.equal(policy({errors:2,hintsUsed:1},[]),2);
assert.equal(policy({errors:4,hintsUsed:2},[]),3);
assert.equal(policy({errors:6,hintsUsed:3,resets:1},[]),4);
assert.equal(policy({errors:4,hintsUsed:2},[{mastery:.9}]),2);
assert.equal(policy({errors:0,hintsUsed:100,resets:100},[]),1);
assert.equal(e.npcSystem.build(p,'intro').maxHintLevel,0);
""")


def test_memory_reload_does_not_repeat_hints_or_rewards():
    node("""
e.state.quests[e.quest(p.id).id]='active';e.state.puzzles[p.id].errors=2;
e.npcSystem.hint(p);const before=e.snapshot();
e.npcSystem.build(p,'hint');assert.deepEqual(e.snapshot(),before);
e.restore(before);assert.deepEqual(e.state.npcMemory,before.npcMemory);
assert.equal(e.state.xp,0);assert.equal(e.state.puzzles[p.id].hintsUsed,0);
""")


def test_stale_dynamic_response_has_no_effect():
    node("""
(async()=>{let finish;let observed=[];
e.npcSystem.configure({profiles:{[p.id]:{mode:'AI_DYNAMIC',role:'engineer'}},provider:c=>new Promise(resolve=>finish=()=>resolve(api.contextualNPC(c)))});
e.npcSystem.present(p,'intro',d=>observed.push(d));await Promise.resolve();
e.npcSystem.cancel();finish();await new Promise(r=>setTimeout(r,10));assert.equal(observed.length,1);
assert.equal(e.state.xp,0);assert.deepEqual(e.state.flags,{});
})().catch(e=>{console.error(e);process.exitCode=1;});
""")


def test_future_boss_phase_cannot_enter_context():
    from mindcrafted.generator.boss_demo import three_phase_blueprint,THREE_PHASE_SOURCE
    from mindcrafted.generator.world_boss import compile_boss
    bp=three_phase_blueprint();w=compile_boss(bp,THREE_PHASE_SOURCE,prior_skills=bp['requiredSkills'])
    node("assert.throws(()=>e.npcSystem.build(e.spec.puzzles[1],'hint'),/FUTURE_PHASE/); const c=e.npcSystem.build(p,'hint');assert.equal(c.phase,'connections');assert(!JSON.stringify(c).includes('configurationRules'));",w)


def test_static_and_contextual_modes_never_need_provider():
    node("""
let calls=0;e.npcSystem.configure({profiles:{[p.id]:{mode:'STATIC'}},provider:()=>{calls++;}});
e.openDialogue(p.id+'_intro');assert.equal(e.dialogueLine().text,e.dialogues.get(p.id+'_intro').lines[0].text);
assert.equal(calls,0);e.advanceDialogue();
e.npcSystem.configure({profiles:{[p.id]:{mode:'CONTEXTUAL',role:'guide'}},provider:()=>{calls++;}});
e.openDialogue(p.id+'_intro');assert.notEqual(e.dialogueLine().text,e.dialogues.get(p.id+'_intro').lines[0].text);assert.equal(calls,0);
""")


def test_client_independently_rejects_commands_spoilers_and_increased_level():
    node("""
const c=e.npcSystem.build(p,'hint'),good=api.contextualNPC(c);
for(const change of [{openDoor:'gate'},{hintLevel:4},{sourceRefs:['fake']},{kind:'narrative_fiction'},{text:p.hint},{text:'La fase futura usa la combinación final.'}])assert.throws(()=>api.validateDialogue({...good,...change},c));
assert.deepEqual(api.validateDialogue(good,c),good);
""")


def test_endpoint_offline_and_explicit_provider(context,monkeypatch):
    import httpx
    from mindcrafted import server
    before=Path('courses.json').read_bytes()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://npc.test') as client:
            monkeypatch.setattr(server.app.state,'npc_dialogue_provider',None,raising=False)
            assert (await client.post('/api/v2/npc-dialogue',json=context)).status_code==503
            assert (await client.post('/api/v2/npc-dialogue',json={'savegame':{}})).status_code==422
            assert (await client.post('/api/v2/npc-dialogue',content='x'*24001)).status_code==413
            provider=ScriptedProvider([contextual(context)])
            monkeypatch.setattr(server.app.state,'npc_dialogue_provider',provider,raising=False)
            result=await client.post('/api/v2/npc-dialogue',json=context)
            assert result.status_code==200 and not result.json()['fallback']
    asyncio.run(run());assert Path('courses.json').read_bytes()==before


def test_planner_profiles_are_declarative_and_bind_objectives():
    from mindcrafted.generator.planner_demo import plan_fixture,SOURCE as source
    from mindcrafted.generator.campaign_plan import validate_plan
    p=plan_fixture();p['regions'][0]['quests'][0]['npc'].update(role='researcher',mode='AI_DYNAMIC')
    assert validate_plan(p,source).regions[0].quests[0].npc.role=='researcher'
    p['regions'][0]['quests'][0]['npc']['setBKT']=True
    with pytest.raises(ValueError):validate_plan(p,source)


def test_large_valid_texts_produce_bounded_unicode_context():
    node("""
p.knowledge.requiredRules=Array.from({length:12},(_,i)=>({id:'rule_'+i,skill:'界'.repeat(1800),description:'界'.repeat(1800),evidence:'界'.repeat(1800)}));
p.objective='界'.repeat(1800);p.hint='界'.repeat(1800);
e.state.puzzles[p.id].errors=8;e.state.puzzles[p.id].hintsUsed=4;e.state.puzzles[p.id].restarts=1;
const c=e.npcSystem.build(p,'hint');assert(new TextEncoder().encode(JSON.stringify(c)).length<=24000);
""")
