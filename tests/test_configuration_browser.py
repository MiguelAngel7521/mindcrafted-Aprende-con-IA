"""Physical selectors, indicators, recovery, BKT and the same WorldEngine/canvas."""
import json
import shutil

from playwright.sync_api import sync_playwright

from mindcrafted.generator import resource_balance
from mindcrafted.generator.resource_balance_demo import SOURCE, blueprint
from mindcrafted.generator.world import compile_world
from mindcrafted.generator.world_package import make_package, render_html
from mindcrafted.generator.world_continuity import install_continuity_guard
from test_world_native_routing import Player


def configuration_journey(tmp_path, design, source, mechanic, bad, good, broken_control):
    world = compile_world(design, source, difficulty='hard')
    puzzle = world['puzzles'][0]; pid = puzzle['id']
    package = make_package(world, source); package['config']['debug'] = True
    html = render_html(package)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium') or shutil.which('chromium-browser'))
        try:
            page = browser.new_page(viewport={'width':1360,'height':1050}, reduced_motion='reduce')
            page.on('pageerror', lambda error: errors.append(str(error)))
            def serve(route):
                if route.request.url == 'http://mindcrafted.test/':
                    route.fulfill(body=html, content_type='text/html')
                else:
                    errors.append('Unexpected request: ' + route.request.url); route.abort()
            page.route('**/*', serve)
            page.goto('http://mindcrafted.test/')
            page.wait_for_function("window.worldEngine && document.getElementById('loading').hidden")
            install_continuity_guard(page)
            player = Player(page, world)
            def state():
                return player.state()['puzzles'][pid]
            def touch(control):
                player.approach(pid + '_' + control); player.press('e')
            def set_control(control, value):
                choices = mechanic.domains(puzzle['mechanics'])[control]
                count = (choices.index(value) - choices.index(state()['configuration'][control])) % len(choices)
                for _ in range(count):
                    touch(control)
                assert state()['configuration'][control] == value
            def bkt():
                return page.evaluate('__MINDCRAFTED_TEST__.getBKT()')
            player.press('ArrowLeft'); player.press('ArrowLeft')
            assert player.state()['player']['x'] == 1
            touch('mentor')
            intro = page.locator('#dialogue-text').inner_text()
            assert intro != puzzle['hint']
            player.finish_dialogue()
            assert player.state()['quests'][pid + '_quest'] == 'active'
            player.walk({(20,9)}); player.press('ArrowRight')
            assert player.state()['player']['x'] == 20
            for control, value in bad.items():
                set_control(control, value)
            touch('console')
            assert not state()['solved'] and state()['attempts'] == state()['errors'] == 1
            assert state()['configuration'] == bad
            assert player.pixel(pid + '_console') == [238,151,122]
            player.approach(pid + '_' + broken_control)
            assert player.pixel(pid + '_' + broken_control) == [238,151,122]
            page.screenshot(path=str(tmp_path / (pid + '-failure.png')), full_page=True)
            failed, observations = state(), bkt()
            player.reload()
            assert state()['effect'] == failed['effect'] and bkt() == observations
            assert any(r['correct'] == 0 for r in observations['records'])
            # Correct directly after the failed activation, then explicitly reset.
            first = next(k for k in good if bad[k] != good[k])
            set_control(first, good[first])
            assert state()['effect'] is None
            player.press('h'); assert page.locator('#feedback').inner_text() != puzzle['hint']
            player.press('r'); assert state()['configuration'] == mechanic.initial(puzzle['mechanics'])
            assert state()['restarts'] == 1
            set_control(first, good[first])
            partial, observations = state()['configuration'], bkt()
            player.reload()
            assert state()['configuration'] == partial and bkt() == observations
            for control, value in good.items():
                set_control(control, value)
            touch('console')
            assert state()['solved'] and player.pixel(pid + '_console') == [134,217,171]
            assert player.state()['quests'][pid + '_quest'] == 'complete'
            assert player.state()['flags'][pid + '_restored']
            player.finish_dialogue(); touch('mentor')
            assert player.state()['dialogue']['id'] == pid + '_after'
            assert page.locator('#dialogue-text').inner_text() != intro
            player.finish_dialogue()
            assert player.state()['flags'][pid + '_understood']
            observations = bkt()
            for record in observations['records']:
                assert record['attempts'] == 2
                assert record['lastObservations']['hintsUsed'] == record['lastObservations']['restarts'] == 1
                assert record['lastObservations']['solutionSteps'] >= 6
            player.walk({(20,9)})
            assert player.pixel(pid + '_gate', 5, 8) == [127,207,159]
            player.press('ArrowRight'); player.press('ArrowRight')
            assert player.state()['player']['x'] == 22
            saved = player.state()
            player.reload(); assert player.state() == saved and bkt() == observations
            touch('console'); player.press('r')
            assert player.state()['xp'] == 75 and len(player.state()['inventory']) == 1 and bkt() == observations
            player.check(); page.set_viewport_size({'width':390,'height':844}); player.check()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path / (pid + '-restored-mobile.png')), full_page=True)
            (tmp_path / (pid + '-e2e.json')).write_text(json.dumps({'ok':True,'partialReload':True,'failedReload':True,'solvedReload':True,'sameCanvas':True,'sameEngine':True,'bkt':observations}, ensure_ascii=False, indent=2))
            assert not errors, errors
        finally:
            browser.close()


def test_resource_balance_physical_journey(tmp_path):
    configuration_journey(tmp_path, blueprint(), SOURCE, resource_balance,
                          {'audio':'fast','control':'fast','report':'archive','copy':'archive'},
                          {'audio':'aux','control':'fast','report':'archive','copy':'archive'}, 'fast')


def test_machine_configuration_physical_journey(tmp_path):
    from mindcrafted.generator import machine_configuration
    from mindcrafted.generator.machine_configuration_demo import blueprint, SOURCE
    configuration_journey(tmp_path, blueprint(), SOURCE, machine_configuration,
                          {'storage':'durable','link':'deferred','mode':'online','cache':'writeback','memory':'medium'},
                          {'storage':'durable','link':'confirmed','mode':'online','cache':'writeback','memory':'medium'}, 'link')
