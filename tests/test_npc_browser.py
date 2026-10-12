"""Physical campaign journey; only the optional provider transport is scripted."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
from playwright.sync_api import sync_playwright
from mindcrafted.generator.world import validate_world
from mindcrafted.generator.world_campaign import assemble_campaign
from mindcrafted.generator.world_package import render_html
from mindcrafted.generator.world_continuity import install_continuity_guard,assert_world_continuity
from mindcrafted.generator.npc_dialogue import NPCDialogueAgent,contextual
from mindcrafted.generator.agent_provider import ScriptedProvider
from mindcrafted.generator.pillar_demo import SOURCE as LESSON_SOURCE
from mindcrafted.generator.boss_demo import THREE_PHASE_SOURCE
from test_boss_campaign import packages
from test_world_native_routing import Player


def test_contextual_npc_campaign_offline_hints_boss_and_reload(tmp_path):
    lesson,boss=packages()
    package=assemble_campaign([lesson,boss],'contextual_npc_journey',development=True)
    package['config']['debug']=True
    package['npcProfiles']={p['world']['id']:{x['id']:{'role':'engineer','mode':'AI_DYNAMIC'} for x in p['world']['puzzles']} for p in (lesson,boss)}
    html=render_html(package);errors=[];contexts=[];responses=[]
    pool=ThreadPoolExecutor(max_workers=1)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium') or shutil.which('chromium-browser'))
        try:
            page=browser.new_page(viewport={'width':1360,'height':1050},reduced_motion='reduce')
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("window.mindcraftedNPCProvider=async(context,{signal})=>{const r=await fetch('/npc',{method:'POST',body:JSON.stringify(context),signal});return r.json();};")
            def serve(route):
                if route.request.url=='http://npc.test/':route.fulfill(body=html,content_type='text/html');return
                if route.request.url=='http://npc.test/npc':
                    context=json.loads(route.request.post_data);contexts.append(context)
                    if len(contexts)>2:route.abort();return  # Internet/provider unavailable.
                    answer=contextual(context);answer['text']=context['allowedTexts'][1]
                    if len(contexts)==2:answer={'openDoor':'exit'}
                    agent=NPCDialogueAgent(ScriptedProvider([answer]))
                    result=pool.submit(lambda:asyncio.run(agent.respond(context))).result(timeout=5);responses.append(result)
                    route.fulfill(body=json.dumps(result),content_type='application/json');return
                route.abort()
            page.route('**/*',serve);page.goto('http://npc.test/')
            page.wait_for_function('window.worldEngine && document.getElementById("loading").hidden')
            install_continuity_guard(page)
            saw_phases=set();injected=False
            for index,(pkg,source) in enumerate([(lesson,LESSON_SOURCE),(boss,THREE_PHASE_SOURCE)]):
                if index:page.evaluate('__WORLD_CONTINUITY__.enterRegion()')
                world=pkg['world'];player=Player(page,world)
                report=validate_world(world,source);assert report['ok'],report['errors']
                for action in report['walkthrough']:
                    if action['type']=='dialogue':
                        state=player.state();pid=state['activePuzzle']
                        # Solved dialogues may refer to the previous phase; inspect their actual NPC.
                        c=page.evaluate("()=>{const d=worldEngine.dialogues.get(worldEngine.state.dialogue.id);const p=worldEngine.puzzles.get(worldEngine.entities.get(d.speaker).puzzleId);return worldEngine.npcSystem.build(p,'reaction');}")
                        if c['phase']:saw_phases.add(c['phase'])
                        if c['bossCompleted']:assert 'Completaste' in page.locator('#dialogue-text').inner_text()
                        player.press('e')
                        if not injected and index==0 and c['puzzle']=='layers' and not state['puzzles']['layers']['solved']:
                            injected=True;position=player.state()['player']
                            for attempt in (1,2):
                                player.approach('layers_console');player.press('e')
                                assert player.state()['puzzles']['layers']['errors']==attempt
                                player.approach('layers_mentor');player.press('e')
                                assert 'no funcionó' in page.locator('#dialogue-text').inner_text()
                                player.finish_dialogue();player.press('h')
                                assert player.state()['npcMemory']['layers']['lastHintLevel']==attempt
                                assert page.locator('#feedback').inner_text()!=world['puzzles'][0]['hint']
                            before=player.state();bkt=page.evaluate('__MINDCRAFTED_TEST__.getBKT()')
                            player.reload()
                            assert player.state()['npcMemory']==before['npcMemory']
                            assert player.state()['puzzles']['layers']['hintsUsed']==2
                            assert page.evaluate('__MINDCRAFTED_TEST__.getBKT()')==bkt
                            player.press('r');player.walk({(position['x'],position['y'])})
                        continue
                    if action['type']=='interact':assert page.evaluate('worldEngine.nearby()[0].id')==action['entityId']
                    page.keyboard.press('Arrow'+action['direction'].capitalize() if action['type']=='move' else 'e')
                    assert_world_continuity(page)
                if index==0:assert page.evaluate('__MINDCRAFTED_TEST__.getCampaign().currentRegion')==1
            assert saw_phases=={'connections','configuration','distribution'}
            final=player.state();bkt=page.evaluate('__MINDCRAFTED_TEST__.getBKT()')
            assert final['bosses']['archive_recovery']['status']=='complete'
            assert final['flags']['archive_recovered']
            player.reload();assert player.state()==final and page.evaluate('__MINDCRAFTED_TEST__.getBKT()')==bkt
            assert page.locator('canvas').count()==1 and page.locator('iframe,#mini-game-overlay').count()==0
            assert responses and not responses[0]['fallback'] and responses[1]['fallback']
            assert all('mechanics' not in c and 'puzzles' not in c for c in contexts)
            assert not errors,errors
            page.screenshot(path=str(tmp_path/'npc-campaign.png'),full_page=True)
        finally:
            browser.close();pool.shutdown(wait=True)
