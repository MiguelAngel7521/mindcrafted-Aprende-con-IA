"""Learn/practice in one region, combine in the next; retain one canvas."""
import json
import pytest
from mindcrafted.generator.pillar_demo import SOURCE as LESSON_SOURCE,blueprint as lessons
from mindcrafted.generator.boss_demo import THREE_PHASE_SOURCE,three_phase_blueprint
from mindcrafted.generator.world_boss import compile_boss
from mindcrafted.generator.world import compile_world
from mindcrafted.generator.world_package import make_package,quality_gate
from mindcrafted.generator.world_campaign import assemble_campaign,write_campaign


def packages():
    lesson=make_package(compile_world(lessons(),LESSON_SOURCE,difficulty='hard'),LESSON_SOURCE,'practice')
    taught={r['skill'] for p in lesson['world']['puzzles'] for r in p['knowledge']['requiredRules']}
    boss=make_package(compile_boss(three_phase_blueprint(),THREE_PHASE_SOURCE,prior_skills=taught),THREE_PHASE_SOURCE,'boss')
    for p in (lesson,boss):p['developmentDemo']=True
    return lesson,boss


def test_composer_requires_actual_previous_lessons_even_for_development():
    lesson,boss=packages()
    with pytest.raises(ValueError,match='habilidades previas'):
        assemble_campaign([boss],development=True)
    campaign=assemble_campaign([lesson,boss],development=True)
    assert len(campaign['campaign']['regions'])==2
    assert len(campaign['regionKnowledge'][1]['skills'])==13


def test_mixed_boss_quality_gate_and_campaign_e2e(tmp_path):
    lesson,boss=packages()
    gate=quality_gate(boss['world'],THREE_PHASE_SOURCE,screenshot=tmp_path/'boss-gate.png')
    assert all(gate['checks'].values()),gate['errors']
    assert gate['boss']['archive_recovery']['recoverable']
    assert gate['e2e']['reload'] and gate['e2e']['recovery']
    assert not gate['approved']  # No fictional model approval.
    boss['quality']=gate
    campaign=assemble_campaign([lesson,boss],'practice_then_combine',development=True)
    manifest=write_campaign(campaign,tmp_path/'campaign',screenshot=tmp_path/'boss-campaign.png')
    assert manifest['checks']['ok'] and manifest['checks']['regions']==2
    assert manifest['checks']['reload'] and manifest['checks']['recovery']
    persisted=json.loads((tmp_path/'campaign/game.pkg.json').read_text())
    assert persisted['regionQuality'][1]['checks']['boss']
