"""Independent, real-keyboard boss journey; never teleport or assign game state."""
import json
import shutil
from playwright.sync_api import sync_playwright

from mindcrafted.generator.world import validate_world
from mindcrafted.generator.world_campaign import assemble_campaign
from test_boss_campaign import packages
from mindcrafted.generator import machine_configuration,resource_balance
from mindcrafted.generator.world_package import render_html
from mindcrafted.generator.world_continuity import install_continuity_guard, assert_world_continuity
from test_world_native_routing import Player


def test_three_phase_boss_physical_failure_recovery_persistence_and_bkt(tmp_path):
    lesson,boss_package=packages()
    world=boss_package['world']
    package=assemble_campaign([lesson,boss_package],'boss_keyboard_journey',development=True)
    package['config']['debug']=True
    html=render_html(package);errors=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,executable_path=shutil.which('chromium') or shutil.which('chromium-browser'))
        try:
            page=browser.new_page(viewport={'width':1360,'height':1050},reduced_motion='reduce')
            page.on('pageerror',lambda error:errors.append(str(error)))
            def serve(route):
                if route.request.url=='http://mindcrafted.test/':route.fulfill(body=html,content_type='text/html')
                else:errors.append('Unexpected request: '+route.request.url);route.abort()
            page.route('**/*',serve);page.goto('http://mindcrafted.test/')
            page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
            install_continuity_guard(page)
            # Earn the prerequisites through actual keyboard gameplay in the previous region.
            from mindcrafted.generator.pillar_demo import SOURCE as lesson_source
            practice=validate_world(lesson['world'],lesson_source)
            assert practice['ok'],practice['errors']
            for action in practice['walkthrough']:
                if action['type']=='interact':
                    assert page.evaluate('worldEngine.nearby()[0].id')==action['entityId']
                page.keyboard.press('Arrow'+action['direction'].capitalize() if action['type']=='move' else 'e')
                assert_world_continuity(page)
            campaign=page.evaluate('__MINDCRAFTED_TEST__.getCampaign()')
            assert campaign['currentRegion']==1 and campaign['regions'][0]['state']['completed']
            assert all(p['solved'] for p in campaign['regions'][0]['state']['puzzles'].values())
            assert set(world['priorSkills']) <= {r['skillId'] for r in page.evaluate('__MINDCRAFTED_TEST__.getBKT()')['records']}
            page.evaluate('__WORLD_CONTINUITY__.enterRegion()')
            player=Player(page,world)
            def touch(id):player.approach(id);player.press('e')
            def boss():return player.state()['bosses']['archive_recovery']
            def bkt():return page.evaluate('__MINDCRAFTED_TEST__.getBKT()')
            def state(pid):return player.state()['puzzles'][pid]
            def set_control(pid,control,value,module):
                m=page.evaluate('id => worldEngine.puzzles.get(id).mechanics',pid)
                choices=module.domains(m)[control]
                for _ in range((choices.index(value)-choices.index(state(pid)['configuration'][control]))%len(choices)):
                    touch(pid+'_'+control)
            touch('layers_mentor');intro=page.locator('#dialogue-text').inner_text();player.finish_dialogue()
            assert player.state()['quests']['layers_quest']=='active'
            assert boss()['phaseIndex']==0 and boss()['status']=='active'
            # Choose Service B deliberately: nine units, rather than the default eight.
            for origin,target in [('UI','ALT'),('ALT','REPO'),('REPO','DB')]:
                touch('layers_'+origin);touch('layers_'+target)
            touch('layers_console');assert state('layers')['solved']
            assert player.pixel('layers_console')==[134,217,171]
            assert boss()['shared']=={'memory_budget':9} and boss()['phaseIndex']==1
            player.finish_dialogue();touch('machine_mentor');player.finish_dialogue()
            assert page.evaluate("worldEngine.puzzles.get('machine').mechanics.configurationRules.find(r=>r.kind==='capacity').max")==9
            before=player.state()['puzzles']['layers']
            bad={'storage':'durable','link':'deferred','mode':'online','cache':'writeback','memory':'medium'}
            for control,value in bad.items():set_control('machine',control,value,machine_configuration)
            touch('machine_console');assert state('machine')['errors']==1 and not state('machine')['solved']
            assert player.pixel('machine_console')==[238,151,122]
            player.approach('machine_link');assert player.pixel('machine_link')==[238,151,122]
            page.screenshot(path=str(tmp_path/'boss-failure.png'),full_page=True)
            player.press('h');assert page.locator('#feedback').inner_text()!=world['puzzles'][2]['hint']
            player.press('r');assert state('machine')['restarts']==1
            assert state('layers')==before and boss()['shared']=={'memory_budget':9}
            set_control('machine','storage','durable',machine_configuration)
            partial=state('machine')['configuration'];mastery=bkt();progress=boss()
            player.reload();assert state('machine')['configuration']==partial and bkt()==mastery and boss()==progress
            good={**bad,'link':'confirmed'}
            for control,value in good.items():set_control('machine',control,value,machine_configuration)
            touch('machine_console');assert state('machine')['solved']
            assert player.pixel('machine_console')==[134,217,171]
            assert boss()['shared']=={'memory_budget':9,'executor_budget':4} and boss()['phaseIndex']==2
            player.finish_dialogue();touch('balance_mentor');player.finish_dialogue()
            allocation={'audio':'fast','control':'aux','report':'archive','copy':'archive'}
            for control,value in allocation.items():set_control('balance',control,value,resource_balance)
            touch('balance_console');assert state('balance')['solved']
            assert boss()['status']=='complete' and player.state()['flags']['archive_recovered']
            player.finish_dialogue();touch('balance_mentor')
            assert player.state()['dialogue']['id']=='balance_after'
            assert page.locator('#dialogue-text').inner_text()!=intro
            player.finish_dialogue();assert player.state()['flags']['balance_understood']
            player.walk({(64,9)})
            assert player.pixel('balance_gate',5,8)==[127,207,159]
            player.press('ArrowRight');player.press('ArrowRight');touch('region_exit')
            assert player.state()['completed'] and player.state()['xp']==350
            final=player.state();mastery=bkt()
            final_campaign=page.evaluate('__MINDCRAFTED_TEST__.getCampaign()')
            for record in mastery['records']:
                context=record['phaseEvidence'][0]
                assert context['bossId']=='archive_recovery'
                assert context['attempts']==(2 if record['skillId'].startswith('configuration.') else 1)
                assert context['observations']['errors']==(1 if record['skillId'].startswith('configuration.') else 0)
            player.reload();assert player.state()==final and bkt()==mastery
            assert page.evaluate('__MINDCRAFTED_TEST__.getCampaign()')==final_campaign
            player.press('r');assert player.state()['xp']==350 and bkt()==mastery
            player.check();assert page.locator('canvas').count()==1
            page.screenshot(path=str(tmp_path/'boss-completed.png'),full_page=True)
            (tmp_path/'boss-e2e.json').write_text(json.dumps({'completed':True,'practicedPreviousRegion':True,'phase1InfluencedPhase2':True,'partialReload':True,
                'solvedReload':True,'sameCanvas':True,'boss':boss(),'bkt':mastery},ensure_ascii=False,indent=2))
            assert not errors,errors
        finally:browser.close()
