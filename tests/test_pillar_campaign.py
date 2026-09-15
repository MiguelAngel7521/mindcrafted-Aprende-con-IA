"""Three archetypes together, repeated IDs across regions, events, BKT and E2E."""
import json

import pytest

from mindcrafted.generator.pillar_demo import SOURCE, blueprint
from mindcrafted.generator.machine_configuration_demo import SOURCE as MACHINE_SOURCE, blueprint as machine_blueprint
from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_campaign import assemble_campaign, write_campaign
from mindcrafted.generator.world_package import make_package, runtime_probe
from test_node_connect_integration import node


@pytest.fixture(scope='module')
def pillar_campaign():
    designs = [(blueprint(), SOURCE), (machine_blueprint(), MACHINE_SOURCE)]
    packages, traces = [], []
    for i, (design, source) in enumerate(designs):
        world = compile_world(design, source, difficulty='hard')
        report = validate_world(world, source)
        assert report['ok'], report['errors']
        assert runtime_probe(world, report['walkthrough'])['ok']
        package = make_package(world, source, 'region_'+str(i))
        package['developmentDemo'] = True
        packages.append(package); traces.append(report['walkthrough'])
    return assemble_campaign(packages, 'three_pillars', development=True), traces


def test_pillar_campaign_isolation_partial_save_events_and_bkt(pillar_campaign):
    package, traces = pillar_campaign
    assert [p['archetype'] for p in package['world']['puzzles']] == ['node_connect','resource_balance','machine_configuration']
    node("""
const assert=require('node:assert/strict');
const {CampaignSession}=require('./mindcrafted/engine/world/campaign.js');
const {SaveSystem}=require('./mindcrafted/engine/world/core.js');
const {createTracker}=require('./mindcrafted/engine/bkt.js');
const {campaign,traces}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const values=new Map(),storage={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};
const session=new CampaignSession(campaign),saves=new SaveSystem(storage,'mixed','hash');
const tracker=createTracker({scope:'mixed',storage}),observations=[],solved=[],transitions=[];
session.events.on('learning.observation',o=>{observations.push([session.index,o]);tracker.observe(o.skill,o.correct,{label:o.label,observations:o.observations});});
session.events.on('puzzle.solved',o=>solved.push([session.index,o.puzzleId]));
session.events.on('campaign.region.changed',o=>transitions.push(o.index));
const pristine=session.snapshot();
let partial=new Set();
for(let region=0;region<traces.length;region++){
 for(const action of traces[region]){
  const e=session.engine;
  if(action.type==='move')assert.equal(e.move(action.direction),true);
  else if(action.type==='interact')assert.equal(e.interact(action.entityId),true);
  else {assert.ok(e.state.dialogue);e.advanceDialogue();}
  for(const p of e.spec.puzzles){
   const s=e.state.puzzles[p.id],key=region+':'+p.id;
   if(!s.solved && !partial.has(key) && (s.connections?.length || Object.values(s.configuration||{}).some(v=>v!==null)) && e.active(p.id)){
    partial.add(key);const before=session.snapshot(),count=observations.length,bkt=tracker.summary();
    saves.save(session);assert.ok(saves.load(session));assert.ok(saves.load(session));
    assert.deepEqual(session.engine.state.puzzles[p.id],before.regions[region].state.puzzles[p.id]);
    assert.equal(observations.length,count);assert.deepEqual(tracker.summary(),bkt);
   }
  }
 }
 assert.equal(session.engine.state.completed,true);
 if(region===0){
  const finished=session.snapshot().regions[0].state;
  assert.ok(session.advance());
  assert.equal(session.index,1);assert.equal(session.engine.state.puzzles.machine.solved,false);
  assert.deepEqual(session.engine.state.flags,{});
  assert.deepEqual(session.engine.state.puzzles.machine,pristine.regions[1].state.puzzles.machine);
  assert.deepEqual(session.snapshot().regions[0].state,finished);
  assert.equal(session.advance(),false);
 }
}
assert.equal(partial.size,4);
assert.equal(session.completed,true);assert.equal(session.xp,300);assert.equal(session.inventory.length,4);
assert.deepEqual(solved,[[0,'layers'],[0,'balance'],[0,'machine'],[1,'machine']]);
assert.equal(observations.length,20);assert.ok(observations.every(([,o])=>o.correct));
const bkt=tracker.summary();assert.equal(bkt.records.length,13);
for(const r of bkt.records)assert.equal(r.attempts,r.skillId.startsWith('configuration.')?2:1);
saves.save(session);assert.ok(saves.load(session));assert.ok(saves.load(session));
assert.equal(observations.length,20);assert.equal(session.xp,300);assert.deepEqual(tracker.summary(),bkt);
assert.equal(transitions.includes(1),true);
""", {'campaign':package['campaign'],'traces':traces})


def test_pillar_campaign_browser_and_region_transition(pillar_campaign, tmp_path):
    package, _ = pillar_campaign
    manifest = write_campaign(package, tmp_path, screenshot=tmp_path/'pillars.png')
    assert manifest['checks']['ok'] and manifest['checks']['regions'] == 2
    assert manifest['checks']['recovery'] and manifest['checks']['reload']
    final = json.loads((tmp_path/'game.pkg.json').read_text())
    assert final['developmentDemo'] is True
    assert all(len(graph['rules']) >= 7 for graph in final['regionKnowledge'])
