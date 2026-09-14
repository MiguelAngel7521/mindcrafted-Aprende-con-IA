"""Regression contracts found during independent World v2 review."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from mindcrafted.generator.world import validate_world
from mindcrafted.generator.world_demo import SOURCE
from mindcrafted.generator.world_schema import WORLD_SCHEMA
from mindcrafted.server import _validate_generation_content


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "mindcrafted/engine/world/core.js"


def test_validator_rejects_control_type_mismatch(world_spec):
    world = deepcopy(world_spec)
    next(entity for entity in world["regions"][0]["entities"] if entity["id"] == "routing_A")["type"] = "switch"
    assert not validate_world(world, SOURCE)["ok"]


def test_validator_rejects_orphan_npc(world_spec):
    world = deepcopy(world_spec)
    world["regions"][0]["entities"].append({"id": "orphan_npc", "type": "npc", "label": "X", "x": 1, "y": 1})
    assert not validate_world(world, SOURCE)["ok"]


def test_validator_rejects_board_map_mismatch(world_spec):
    world = deepcopy(world_spec)
    puzzle = next(puzzle for puzzle in world["puzzles"] if puzzle["archetype"] == "push_blocks")
    x = puzzle["world"]["offset"]["x"] + 1
    y = puzzle["world"]["offset"]["y"] + 2
    row = list(world["regions"][0]["tiles"][y])
    assert row[x] == "."
    row[x] = "#"
    world["regions"][0]["tiles"][y] = "".join(row)
    assert not validate_world(world, SOURCE)["ok"]


def test_current_puzzle_uses_two_dimensional_proximity(world_spec):
    world = deepcopy(world_spec)
    next(entity for entity in world["regions"][0]["entities"] if entity["id"] == "sequence_console").update(x=7, y=8)
    script = (
        "const {WorldEngine}=require(process.argv[1]);"
        "const world=JSON.parse(require('node:fs').readFileSync(0,'utf8'));"
        "const engine=new WorldEngine(world);"
        "engine.state.player={x:7,y:7,direction:'down'};"
        "process.stdout.write(engine.currentPuzzle().id);"
    )
    result = subprocess.run(["node", "-e", script, str(CORE)], input=json.dumps(world),
                            text=True, capture_output=True, check=True)
    assert result.stdout == "sequence"


def test_schema_matches_single_region_runtime_contract():
    assert WORLD_SCHEMA["properties"]["regions"]["maxItems"] == 1


def test_world_api_rejects_short_lessons_before_generation():
    content = {"course": {"title": "T", "gameplay": "world"},
               "chunks": [{"id": "c1", "title": "T", "content": "x"}]}
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match="60 caracteres"):
        _validate_generation_content(content)


def test_restore_preserves_flags_set_by_intro_dialogue(world_spec):
    world = deepcopy(world_spec)
    world["dialogues"][0]["onComplete"].append({"type": "setFlag", "target": "review_memory"})
    report = validate_world(world, SOURCE)
    assert report["ok"], report["errors"]
    script = (
        "const {WorldEngine}=require(process.argv[1]);"
        "const data=JSON.parse(require('node:fs').readFileSync(0,'utf8'));"
        "const engine=new WorldEngine(data.world);"
        "for(const action of data.walkthrough){"
        "if(action.type==='move')engine.move(action.direction);"
        "else if(action.type==='interact')engine.interact(action.entityId);"
        "else engine.advanceDialogue();}"
        "const saved=engine.snapshot(); const restored=new WorldEngine(data.world);"
        "restored.restore(saved);"
        "process.stdout.write(JSON.stringify({before:saved.flags.review_memory,after:restored.state.flags.review_memory}));"
    )
    result = subprocess.run(["node", "-e", script, str(CORE)],
                            input=json.dumps({"world": world, "walkthrough": report["walkthrough"]}),
                            text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)["after"] is True
