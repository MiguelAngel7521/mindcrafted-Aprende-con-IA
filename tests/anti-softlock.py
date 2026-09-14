def test_mandatory_puzzles_can_be_reset(world_spec):

    for puzzle in world_spec["puzzles"]:

        if not puzzle.get("mandatory"):
            continue

        assert (
            puzzle.get("resettable") is True
            or puzzle.get("failure", {}).get("autoReset") is True
        ), f"{puzzle['id']} puede provocar softlock"