import json
import pytest


def all_entities(world):
    result = {}

    for region in world["regions"]:
        for entity in region.get("entities", []):
            result[entity["id"]] = entity

    return result


def all_dialogues(world):
    return {d["id"]: d for d in world.get("dialogues", [])}


def test_world_has_controllable_player(world_spec):
    assert "player" in world_spec

    player = world_spec["player"]

    assert player["controllable"] is True
    assert player.get("spawnRegion")
    assert isinstance(player.get("x"), (int, float))
    assert isinstance(player.get("y"), (int, float))


def test_every_puzzle_runs_inside_world(world_spec):
    for puzzle in world_spec.get("puzzles", []):
        assert puzzle["runtime"] == "world", (
            f"{puzzle['id']} intenta ejecutar un minijuego externo"
        )


def test_every_puzzle_has_world_anchor(world_spec):
    entities = all_entities(world_spec)

    for puzzle in world_spec.get("puzzles", []):
        anchor = puzzle.get("world", {}).get("anchorEntity")

        assert anchor, (
            f"{puzzle['id']} no tiene anchorEntity"
        )

        assert anchor in entities, (
            f"{puzzle['id']} apunta a entidad inexistente: {anchor}"
        )


def test_no_overlay_minigames(world_spec):
    raw = json.dumps(world_spec).lower()

    forbidden = [
        "mini-game-overlay",
        "launchminigame",
        "screen_minigame",
        "modal_minigame"
    ]

    for token in forbidden:
        assert token not in raw, (
            f"Se encontró arquitectura de minijuego externo: {token}"
        )


def test_dialogue_references_exist(world_spec):
    dialogues = all_dialogues(world_spec)

    for puzzle in world_spec.get("puzzles", []):
        success_dialogue = (
            puzzle
            .get("success", {})
            .get("dialogue")
        )

        if success_dialogue:
            assert success_dialogue in dialogues


def test_every_puzzle_teaches_a_real_concept(world_spec):
    for puzzle in world_spec.get("puzzles", []):
        knowledge = puzzle.get("knowledge", {})

        assert knowledge.get("concept")
        assert knowledge.get("learning_action")

        assert len(knowledge["learning_action"]) >= 15