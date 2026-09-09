import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from mindcrafted.generator import pipeline
from mindcrafted.generator.practice import load_world, validate_plan
from mindcrafted.generator.adventure import layout
from mindcrafted.generator.adventure_rules import validate_technical
from mindcrafted.generator.boss import build_boss
from practice_fixtures import SOURCES, TECH_SOURCE, fixture, technology_fixture


class AdventureTests(unittest.IsolatedAsyncioTestCase):
    def test_technical_models_reject_unreachable_routes_and_calculate_states(self):
        plan=validate_plan(technology_fixture(),TECH_SOURCE,'Redes')
        self.assertEqual(plan['world'],'technology')
        self.assertEqual(plan['puzzles'][1]['data']['states'],[5,10,9])
        data=deepcopy(plan['puzzles'][0]['data']);data['edges']=[[0,1],[1,0]]
        with self.assertRaisesRegex(ValueError,'ruta'):validate_technical('packet_route',data)
        data=dict(initial=9,operations=[dict(op='multiply',value=9)]*3)
        with self.assertRaisesRegex(ValueError,'estados'):validate_technical('algorithm_trace',data)

    def test_all_worlds_fit_five_stations_and_seed_is_reproducible(self):
        puzzles=[dict(id=f'p{i}',title=f'Misión {i}') for i in range(5)]
        for world_id in ('technology','laboratory','mathematics','biology'):
            world=load_world(world_id)
            for seed in (1,10,1234):
                result=layout(world,puzzles,seed)
                self.assertEqual(result,layout(world,puzzles,seed))
                self.assertEqual(len({(s['x'],s['y']) for s in result['stations']}),5)
                self.assertTrue(all(s['objectId'] for s in result['stations']))
                self.assertTrue(all((result['exit']['x']-s['x'])**2+(result['exit']['y']-s['y'])**2>72**2 for s in result['stations']))
            blocked=deepcopy(world)
            next(l for l in blocked['map']['layers'] if l['name']=='Colisiones')['objects'].append(dict(x=0,y=0,width=768,height=512))
            with self.assertRaisesRegex(ValueError,'inicio'):layout(blocked,puzzles,1)

    async def test_override_and_boss_keep_validated_source_in_export(self):
        async def fake(*a,**k):return json.dumps(technology_fixture())
        with tempfile.TemporaryDirectory() as tmp,patch.object(pipeline,'_bind_api_config',return_value=fake):
            html=await pipeline.generate_game(TECH_SOURCE,tmp,world_override='mathematics',difficulty='study')
            pkg=json.loads((Path(tmp)/'game.pkg.json').read_text())
            self.assertEqual(pkg['config']['practice']['world'],'mathematics')
            self.assertEqual(pkg['config']['adventure']['difficulty'],'study')
            boss=build_boss([pkg],42)
            self.assertEqual(boss,build_boss([pkg],42))
            self.assertEqual(len(boss['phases']),3)
            self.assertTrue(all(p['evidence'] in TECH_SOURCE for p in boss['phases']))
            self.assertIn('AdventureEncounters',Path(html).read_text())
            self.assertNotIn('src="/engine/adventure/',Path(html).read_text())

    def test_simulation_and_eight_rules_in_node(self):
        subprocess.run(['node','tests/check_adventure_models.cjs'],check=True,capture_output=True,text=True)


if __name__=='__main__':unittest.main()
