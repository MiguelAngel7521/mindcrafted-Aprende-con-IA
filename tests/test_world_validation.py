from copy import deepcopy

import pytest

from mindcrafted.generator.world import compile_world, validate_world
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint
from mindcrafted.generator.world_package import CHECKS, check_judge, make_package, quality_gate, write_world_package


@pytest.mark.parametrize("kind", ["route_network", "switch_sequence", "push_blocks"])
def test_each_archetype_compiles_and_has_nontrivial_solution(kind):
    world = compile_world(demo_blueprint((kind,)), SOURCE)
    report = validate_world(world, SOURCE)
    assert report["ok"], report["errors"]
    solution = next(iter(report["solutions"].values()))
    assert solution["steps"] >= 4
    assert 0 < solution["randomSuccessProbability"] <= 0.1


@pytest.mark.parametrize("mutation", [
    lambda w: w.update(regions=[]),
    lambda w: w.update(puzzles=[]),
    lambda w: w["puzzles"][0].update(runtime="overlay"),
    lambda w: w["puzzles"][0].update(archetype="multiple_choice"),
    lambda w: w["puzzles"][0].update(archetype="custom_world_puzzle"),
    lambda w: w["puzzles"][0].update(javascript="alert(1)"),
    lambda w: w["puzzles"][0]["world"].update(anchorEntity="missing"),
    lambda w: w["puzzles"][0]["success"].update(openEntity="missing"),
    lambda w: w["puzzles"][0]["success"].update(dialogue="missing"),
    lambda w: w["puzzles"][0]["knowledge"]["requiredRules"][0].update(evidence="Esto no aparece en los apuntes originales"),
    lambda w: w["puzzles"][0]["mechanics"]["edges"][0].update(target="missing"),
    lambda w: w["puzzles"][0].update(resettable=False),
    lambda w: w["player"].update(x=-1),
    lambda w: w["regions"][0]["entities"].append(deepcopy(w["regions"][0]["entities"][0])),
    lambda w: w["regions"][0]["entities"][0].update(dialogueId="missing"),
    lambda w: w["dialogues"][0]["onComplete"].append({"type":"setFlag","target":"routing_restored"}),
])
def test_rejects_invalid_world_contracts(world_spec, mutation):
    mutation(world_spec)
    assert not validate_world(world_spec, SOURCE)["ok"]


def test_rejects_softlocked_anchor(world_spec):
    region = world_spec["regions"][0]
    # Seal the only passage to the console, regardless of the LLM's opinion.
    for y in range(region["height"]):
        row = list(region["tiles"][y]); row[6] = "#"; region["tiles"][y] = "".join(row)
    report = validate_world(world_spec, SOURCE)
    assert not report["ok"]
    assert "Softlock" in " ".join(report["errors"])


def test_rejects_deadlock_in_dependency_sequence():
    blueprint = demo_blueprint(("switch_sequence",))
    blueprint["puzzles"][0]["mechanics"]["constraints"].append({"before":"deliver","after":"address","ruleId":"address_first"})
    with pytest.raises(ValueError, match="cíclica"):
        compile_world(blueprint, SOURCE)


def test_rejects_decorative_knowledge_rule():
    blueprint = demo_blueprint()
    p = blueprint["puzzles"][0]
    p["knowledge"]["requiredRules"].append(dict(p["knowledge"]["requiredRules"][0], id="decorative"))
    p["mechanics"]["nodes"][0]["ruleId"] = "decorative"  # source A never reaches its capacity
    with pytest.raises(ValueError, match="prescindible"):
        compile_world(blueprint, SOURCE)


def judge(score=22, approved=True, issues=None):
    return {"approved": approved, "scores": {k: score for k in ("embodiedLearning","worldIntegration","interactionQuality","technicalSolvability")}, "issues": issues or []}


@pytest.mark.parametrize("verdict", [judge(21), judge(25, False), judge(25, issues=["concepto decorativo"]), {}, judge(True), judge(26)])
def test_judge_cannot_approve_bad_scores_or_invalid_data(verdict):
    try:
        assert not check_judge(verdict)
    except ValueError:
        pass


def test_unrun_checks_cannot_publish_even_with_perfect_judge(world_spec, tmp_path):
    report = quality_gate(world_spec, SOURCE, judge=judge(25), run_probes=False)
    assert not report["approved"]
    assert report["checks"]["runtime"] is False
    assert report["checks"]["e2e"] is False
    with pytest.raises(ValueError, match="QualityGate"):
        write_world_package(make_package(world_spec, SOURCE), SOURCE, report, tmp_path)
    assert not list(tmp_path.iterdir())


def test_perfect_judge_never_overrides_schema_failure(world_spec):
    world_spec["puzzles"][0]["runtime"] = "modal_minigame"
    report = quality_gate(world_spec, SOURCE, judge=judge(25), run_probes=False)
    assert not report["approved"]


def test_each_gate_is_required(world_spec, tmp_path):
    from mindcrafted.generator.world import world_hash
    package = make_package(world_spec, SOURCE)
    for missing in CHECKS:
        report = {"approved":True,"worldHash":world_hash(world_spec),"judge":judge(),"errors":[],"checks":dict.fromkeys(CHECKS, True)}
        report["checks"][missing] = False
        with pytest.raises(ValueError):
            write_world_package(package, SOURCE, report, tmp_path)
    assert not list(tmp_path.iterdir())
