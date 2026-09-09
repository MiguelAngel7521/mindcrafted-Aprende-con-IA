import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mindcrafted.generator import pipeline
from mindcrafted.generator.practice import validate_plan, allowed_kinds, render_html
from mindcrafted.generator.course_pipeline import generate_course_with_platform
from practice_fixtures import SOURCES, fixture


class PracticeTests(unittest.IsolatedAsyncioTestCase):
    def test_subjects_select_distinct_mechanics_and_worlds(self):
        kinds = set()
        for world, source in SOURCES.items():
            plan = validate_plan(fixture(world), source, 'Lección')
            self.assertEqual(plan['world'], world)
            kinds.update(p['kind'] for p in plan['puzzles'])
        self.assertEqual(len(kinds), 6)
        self.assertNotIn('circuit_target', allowed_kinds(SOURCES['biology']))
        self.assertNotIn('balance_equation', allowed_kinds(SOURCES['biology']))

    def test_rejects_unfounded_duplicate_and_unsolvable_puzzles(self):
        for mutate in [
            lambda p: p['puzzles'][0].update(evidence='Esta frase no aparece en los apuntes originales.'),
            lambda p: p['puzzles'][0]['data'].update(c=15),
            lambda p: p['puzzles'][1]['data'].update(numerator=4),
            lambda p: p['puzzles'][2]['data'].update(answer=True),
            lambda p: p['puzzles'].__setitem__(2, p['puzzles'][0]),
        ]:
            plan = fixture(); mutate(plan)
            with self.assertRaises(ValueError):
                validate_plan(plan, SOURCES['mathematics'], 'Lección')
        plan = fixture('laboratory')
        with self.assertRaisesRegex(ValueError, 'mecánica'):
            validate_plan(plan, SOURCES['biology'], 'Lección')

    def test_answers_are_calculated_locally_and_json_cannot_close_script(self):
        plan = fixture(); plan['puzzles'][0]['data']['solution'] = 99
        validated = validate_plan(plan, SOURCES['mathematics'], 'Lección')
        self.assertEqual(validated['puzzles'][0]['data']['solution'], 5)
        html = render_html({'config': {'title': '</script><script>alert(1)</script>'}})
        self.assertNotIn('</script><script>alert(1)', html)
        self.assertIn('\\u003c/script\\u003e', html)

    async def test_generation_embeds_art_and_uses_real_notes(self):
        calls = []
        async def fake(prompt, system, **kwargs):
            calls.append((prompt, system, kwargs))
            return json.dumps(fixture())
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(pipeline, '_bind_api_config', return_value=fake):
                path = await pipeline.generate_game('Título orientativo', tmp, source_text=SOURCES['mathematics'], forced_title='Mi lección')
            pkg = json.loads((Path(tmp)/'game.pkg.json').read_text())
            self.assertEqual(len(calls), 1)
            self.assertIn(SOURCES['mathematics'], calls[0][0])
            self.assertEqual(pkg['config']['generationMode'], 'aventura')
            self.assertEqual(pkg['config']['totalChapters'], 3)
            self.assertEqual(pkg['config']['practice']['title'], 'Mi lección')
            self.assertTrue(pkg['config']['pixelWorld']['assets']['explorer']['image'].startswith('data:image/png;base64,'))
            self.assertIn('adventure-data', Path(path).read_text())
            self.assertNotIn('src="/engine/adventure/runtime.js"', Path(path).read_text())
            self.assertEqual(len(pkg['config']['adventure']['layout']['stations']),3)
            self.assertEqual(len(pkg['config']['boss']['phases']),3)
            self.assertTrue((Path(tmp)/'practice-plan.json').exists())
            self.assertTrue((Path(tmp)/'cover.js').exists())

    async def test_one_repair_then_fails_without_generic_fallback(self):
        for repair in (True, False):
            calls = []
            async def fake(*args, **kwargs):
                calls.append(1)
                return json.dumps(fixture()) if repair and len(calls) == 2 else '{}'
            with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline, '_bind_api_config', return_value=fake):
                if repair:
                    await pipeline.generate_game(SOURCES['mathematics'], tmp)
                else:
                    with self.assertRaisesRegex(ValueError, 'fieles'):
                        await pipeline.generate_game(SOURCES['mathematics'], tmp)
                    self.assertFalse((Path(tmp)/'game.pkg.json').exists())
                self.assertEqual(len(calls), 2)

    async def test_course_preserves_order_skips_failures_and_propagates_subject(self):
        calls=[]
        async def fake(prompt, system, **kwargs):
            calls.append(prompt)
            if 'material insuficiente' in prompt: return '{}'
            return json.dumps(fixture())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); content=root/'content.json'; out=root/'curso-test'
            content.write_text(json.dumps({'course':{'title':'Práctica','subject':'Álgebra escolar'},'chunks':[
                {'id':id,'title':id,'content':source} for id,source in [('chunk-2',SOURCES['mathematics']),('fallo','material insuficiente '*5),('chunk-10',SOURCES['mathematics'])]
            ]}))
            with patch.object(pipeline, '_bind_api_config', return_value=fake):
                await generate_course_with_platform(str(content),str(out))
            manifest=json.loads((out/'course-manifest.json').read_text())
            self.assertEqual([g['status'] for g in manifest['games']],['success','failed','success'])
            self.assertEqual(manifest['games'][0]['puzzle_count'],3)
            self.assertIn('Álgebra escolar',calls[0])
            self.assertIn('balance_equation',calls[-1])
            pkg=json.loads((out/'games/chunk-2/game.pkg.json').read_text())
            self.assertEqual(pkg['config']['courseId'],'curso-test')
            self.assertEqual(pkg['config']['nextGameUrl'],'/play?course=curso-test&game=chunk-10')
            last=json.loads((out/'games/chunk-10/game.pkg.json').read_text())
            self.assertNotIn('nextGameUrl',last['config'])
            self.assertIsNone(pkg['config']['boss'])
            self.assertTrue(last['config']['boss']['partial'])
            self.assertEqual([r['chunkId'] for r in last['config']['courseRoute']],['chunk-2','chunk-10'])
            self.assertTrue((out/'index.html').exists())

if __name__ == '__main__': unittest.main()
