def test_puzzle_changes_world_state(world_spec):
    for puzzle in world_spec["puzzles"]:

        success = puzzle.get("success", {})

        changes_world = any([
            success.get("setFlags"),
            success.get("openEntity"),
            success.get("spawnEntity"),
            success.get("removeEntity"),
            success.get("unlockRegion")
        ])

        assert changes_world, (
            f"{puzzle['id']} se puede completar "
            "pero no produce ninguna consecuencia en el mundo"
        )