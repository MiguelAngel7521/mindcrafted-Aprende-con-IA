"""Deterministic policy, verified variants, immutability and browser trajectories."""
from copy import deepcopy
import json
import subprocess
import shutil
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from mindcrafted.generator.adaptive_difficulty import recommend_difficulty, parameters, verify_catalog, attach_variants
from mindcrafted.generator.node_connect_demo import blueprint, SOURCE
from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_package import make_package, render_html
from mindcrafted.generator.world_campaign import assemble_campaign
from test_world_native_routing import Player
from mindcrafted.generator.world_continuity import install_continuity_guard


def context(strong=True):
    return dict(challengeId='next', objective='layers', archetype='node_connect',
                records=[dict(skill='layers',mastery=.9 if strong else .3,attempts=4)],
                history=[dict(id=str(i),success=True,errors=0 if strong else 3,hints=0 if strong else 2,resets=0 if strong else 1) for i in range(2)])


def test_policy_two_trajectories_same_objective_and_determinism():
    a,b=recommend_difficulty(context()),recommend_difficulty(context(False))
    assert a['selectedDifficulty']=='HARD' and b['selectedDifficulty']=='EASY'
    assert a['objective']==b['objective'] and a==recommend_difficulty(context())
    assert a['parameters']['initialHintLevel']==b['parameters']['initialHintLevel']==1


def test_cold_start_cooldown_and_no_oscillation():
    c=context();c['records']=[]
    assert recommend_difficulty(c)['reasons']==['INSUFFICIENT_MASTERY_EVIDENCE']
    c=context(False);c.update(previous='HARD',sinceChange=0)
    assert recommend_difficulty(c)['selectedDifficulty']=='HARD'
    c['sinceChange']=2
    assert recommend_difficulty(c)['selectedDifficulty']=='NORMAL'
    c=context();c['previous']='EASY'
    assert recommend_difficulty(c)['selectedDifficulty']=='NORMAL'


@pytest.mark.parametrize('change',[
    {'records':[{'skill':'x','mastery':2,'attempts':4}]}, {'records':[{'skill':'x','mastery':float('nan'),'attempts':4}]},
    {'policy':{'maxStepChange':2}}, {'policy':{'minDifficulty':'EXPERT'}}, {'policy':{'low':.9,'high':.5}},
    {'archetype':'quiz'}, {'previous':'EXPERT'}, {'objective':''}, {'policy':{'openDoor':'gate'}},
    {'history':[{'id':'same','success':True,'errors':-1,'hints':0,'resets':0}]}])
def test_invalid_policy_evidence_and_parameters(change):
    c=context();c.update(change)
    with pytest.raises(ValueError):recommend_difficulty(c)


def test_ai_cannot_override_policy():
    c=context();suggestion=recommend_difficulty(c);suggestion['selectedDifficulty']='EASY'
    with pytest.raises(ValueError,match='AI_DIFFICULTY_POLICY_VIOLATION'):recommend_difficulty(c,suggestion)


def worlds():
    result={}
    for level,count in [('EASY',6),('NORMAL',8),('HARD',11)]:
        b=blueprint();b['puzzles'][0]['mechanics']['edges']=b['puzzles'][0]['mechanics']['edges'][:count]
        result[level]=compile_world(b,SOURCE,difficulty={'EASY':'study','NORMAL':'normal','HARD':'hard'}[level])
    return result


def catalog():
    from mindcrafted.generator.world import world_hash
    return {'policyVersion':1,'objective':blueprint()['puzzles'][0]['objective'],'base':'NORMAL','variants':[
        {'level':level,'world':w,'worldHash':world_hash(w),'parameters':parameters(w)} for level,w in worlds().items()]}


@pytest.mark.parametrize('kind',['node_connect','resource_balance','machine_configuration'])
def test_archetype_specific_parameters(kind):
    from importlib import import_module
    demo=import_module('mindcrafted.generator.'+kind+'_demo')
    w=compile_world(demo.blueprint(),demo.SOURCE);m=parameters(w)
    assert m['choiceCount']>0 and m['constraintCount']>=3 and m['conceptCombinationCount']>=3


@pytest.mark.parametrize('attack',['objective','parameters','unsolvable','ordering','boss'])
def test_variant_contract_rejects_bad_content(attack):
    from mindcrafted.generator.world import world_hash
    c=catalog();v=c['variants'][0]
    if attack=='objective':v['world']['puzzles'][0]['objective']='A different academic objective'
    elif attack=='parameters':v['parameters']['choiceCount']=999
    elif attack=='unsolvable':v['world']['puzzles'][0]['mechanics']['edges']=[]
    elif attack=='ordering':c['variants'].reverse()
    else:v['world']['puzzles'].append(deepcopy(v['world']['puzzles'][0]))
    v['worldHash']=world_hash(v['world'])
    with pytest.raises(ValueError):verify_catalog(c,SOURCE)


@pytest.fixture(scope='module')
def adaptive_package():
    ws=worlds();packages=[]
    for i in range(3):
        p=make_package(ws['NORMAL'],SOURCE,f'practice_{i}');p['developmentDemo']=True;packages.append(p)
    p=assemble_campaign(packages,'adaptive_fixture',development=True)
    p=attach_variants(p,2,ws,SOURCE);p['config']['debug']=True
    return p


def test_campaign_mid_puzzle_immutability_and_restore(adaptive_package):
    path=Path('mindcrafted/engine/world/campaign.js').resolve()
    script="""const {CampaignSession}=require(process.argv[1]);let data='';process.stdin.on('data',s=>data+=s);process.stdin.on('end',()=>{
    const p=JSON.parse(data),s=new CampaignSession(p.campaign);let rejected=false;
    try{s.selectNext(1)}catch(e){rejected=e.message==='MID_PUZZLE_ADAPTATION_FORBIDDEN'}
    if(!rejected)throw Error('mid-puzzle accepted');
    const before=JSON.stringify(s.engine.spec);s.readMastery=()=>({mastery:.99,attempts:50});
    if(JSON.stringify(s.engine.spec)!==before)throw Error('rules changed');console.log('ok');});"""
    r=subprocess.run(['node','-e',script,str(path)],input=json.dumps(adaptive_package),text=True,capture_output=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('struggling',[False,True])
def test_browser_two_profiles_freeze_reload_npc(adaptive_package,struggling):
    html=render_html(adaptive_package);errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium') or shutil.which('chromium-browser'))
        try:
            page=browser.new_page(viewport={'width':1360,'height':1050},reduced_motion='reduce')
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/*',lambda route:route.fulfill(body=html,content_type='text/html') if route.request.url=='http://adaptive.test/' else route.abort())
            page.goto('http://adaptive.test/');page.wait_for_function('window.worldEngine')
            install_continuity_guard(page)
            canvas=page.locator('canvas').element_handle()
            for region in range(3):
                if region:page.evaluate("__WORLD_CONTINUITY__.enterRegion()")
                w=page.evaluate('worldEngine.spec');report=validate_world(w,SOURCE);assert report['ok']
                player=Player(page,w);injected=False
                if region==2:
                    decision=page.evaluate('worldEngine.difficultyDecision')
                    assert decision['selectedDifficulty']==('EASY' if struggling else 'HARD'),decision
                    assert len(w['puzzles'][0]['mechanics']['edges'])==(6 if struggling else 11)
                    before=page.evaluate('__MINDCRAFTED_TEST__.getCampaign()')
                    # Changing later mastery must not alter the already selected world on reload.
                    page.evaluate("()=>{const key='mindcrafted_bkt_v1',v=JSON.parse(localStorage.getItem(key));for(const r of Object.values(v.skills))r.mastery=.1;localStorage.setItem(key,JSON.stringify(v));}")
                    player.reload()
                    assert page.evaluate('worldEngine.spec')==w
                    assert page.evaluate('worldEngine.difficultyDecision')==decision
                    assert page.evaluate('__MINDCRAFTED_TEST__.getCampaign()')==before
                    canvas=page.locator('canvas').element_handle()
                for action in report['walkthrough']:
                    if action['type']=='dialogue':
                        if region==2 and not injected:
                            text=page.locator('#dialogue-text').inner_text()
                            assert ('menos opciones' if struggling else 'más alternativas') in text
                        player.press('e')
                        if not injected:
                            injected=True
                            if region==2:
                                pos=player.state()['player'];player.approach('layers_console')
                                for _ in range(4):player.press('e')
                                player.press('h')
                                assert page.evaluate('worldEngine.spec')==w
                                saved=player.state();player.reload()
                                assert page.evaluate('worldEngine.spec')==w
                                assert page.evaluate('worldEngine.difficultyDecision')==decision
                                assert player.state()['puzzles']['layers']['errors']==saved['puzzles']['layers']['errors']
                                player.walk({(pos['x'],pos['y'])})
                                canvas=page.locator('canvas').element_handle()
                            if struggling and region<2:
                                pos=player.state()['player'];player.approach('layers_console')
                                for _ in range(3):player.press('e')
                                player.press('h');player.press('h');player.press('r')
                                player.walk({(pos['x'],pos['y'])})
                        continue
                    page.keyboard.press('Arrow'+action['direction'].capitalize() if action['type']=='move' else 'e')
                    assert page.evaluate('(c)=>c===document.querySelector("canvas")',canvas)
            assert page.evaluate('__MINDCRAFTED_TEST__.getCampaign().regions.every(r=>r.state.completed)')
            bkt=page.evaluate('__MINDCRAFTED_TEST__.getBKT()');player.reload()
            assert page.evaluate('__MINDCRAFTED_TEST__.getBKT()')==bkt
            assert page.locator('canvas').count()==1 and page.locator('iframe,#mini-game-overlay').count()==0
            assert not errors,errors
        finally:browser.close()


def test_adaptive_export_and_missing_gate_rejection(adaptive_package,tmp_path):
    from mindcrafted.generator.world_campaign import write_campaign
    bad=deepcopy(adaptive_package);bad['adaptiveQuality']={}
    with pytest.raises(ValueError,match='ADAPTATION_QUALITY_GATE_REQUIRED'):
        write_campaign(bad,tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    report=write_campaign(adaptive_package,tmp_path/'adaptive-build')
    assert report['checks']['ok'] and report['checks']['regions']==3


def test_real_publication_is_not_implied_by_development_variants(adaptive_package,tmp_path):
    from mindcrafted.generator.world_campaign import write_campaign
    real=deepcopy(adaptive_package);real['developmentDemo']=False
    with pytest.raises(ValueError,match='VARIANT_JUDGES'):
        write_campaign(real,tmp_path/'real')
    assert not (tmp_path/'real').exists()


@pytest.mark.parametrize('kind',['resource_balance','machine_configuration'])
def test_all_archetypes_have_verified_adaptive_variants(kind):
    """Authored test scenarios, not real material or AI publication evidence."""
    from importlib import import_module
    from mindcrafted.generator.world import world_hash
    from mindcrafted.generator.world_package import quality_gate, CHECKS
    demo=import_module('mindcrafted.generator.'+kind+'_demo')
    source=demo.SOURCE
    if kind=='resource_balance':
        source=source.replace('El sistema reparte cuatro cargas indivisibles entre tres ejecutores.',
                              'El taller presenta subconjuntos de estas cargas indivisibles y ejecutores para practicar el reparto.')
        source+='Auxiliar II también es un recurso de baja latencia equivalente con capacidad de cuatro unidades.\n'
    variants=[]
    for level in ('EASY','NORMAL','HARD'):
        b=demo.blueprint();p=b['puzzles'][0];m=p['mechanics']
        if kind=='resource_balance':
            if level=='EASY':m['loads']=m['loads'][:3]
            if level=='HARD':
                m['targets'].append({'id':'aux2','label':'Auxiliar II','kind':'low_latency'})
                m['allocationRules'][1]['limits'].append({'target':'aux2','min':0,'max':4})
            p['hint']='Reparte Audio y Control entre Rápido y Auxiliar. Las cargas por lotes presentes pueden ir a Archivo.'
        else:
            values=m['parameters'][0]['values']
            if level=='EASY':values[:]=[v for v in values if v['id']!='diagnostic']
            if level=='HARD':values.append({'id':'suspended','label':'Suspendido','quantity':None})
        w=compile_world(b,source,difficulty={'EASY':'study','NORMAL':'normal','HARD':'hard'}[level])
        gate=quality_gate(w,source)
        assert not gate['errors'] and all(gate['checks'][k] for k in CHECKS),gate
        variants.append({'level':level,'world':w,'worldHash':world_hash(w),'parameters':parameters(w)})
    verify_catalog({'policyVersion':1,'objective':p['objective'],'base':'NORMAL','variants':variants},source)
