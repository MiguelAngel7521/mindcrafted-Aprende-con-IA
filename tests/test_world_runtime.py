import json
import subprocess
from pathlib import Path

from mindcrafted.generator.world import validate_world
from mindcrafted.generator.world_demo import SOURCE
from mindcrafted.generator.world_package import runtime_probe

ROOT = Path(__file__).resolve().parents[1]


def test_real_runtime_completes_all_archetypes(world_spec):
    report = validate_world(world_spec, SOURCE)
    result = runtime_probe(world_spec, report["walkthrough"])
    assert result["ok"]
    assert result["observations"] == 8


def test_errors_reset_save_and_learning(world_spec):
    result = subprocess.run(["node", str(ROOT / "tests/check_world_state.cjs")], input=json.dumps(world_spec),
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
