"""Proof bounds, genuinely restrictive knowledge, direction and graph constraints."""
from copy import deepcopy
from itertools import product

import pytest

from mindcrafted.generator.node_connect import simulate, solve, validate
from mindcrafted.generator.node_connect_demo import blueprint
from test_node_connect_integration import node


def puzzle():
    return deepcopy(blueprint()["puzzles"][0])


def test_exhaustive_proof_recognizes_alternatives_and_reproducible_random_metric():
    p = puzzle()
    proof = solve(p)
    assert proof == solve(p)
    assert proof["evaluatedStates"] == 2048
    assert proof["solutionCount"] == 4
    assert proof["steps"] == 7
    assert proof["randomSuccessProbability"] == 4 / 2048
    assert 0 <= proof["randomSuccessRate"] < .1
    assert proof["randomTrials"] == 256
    assert proof["solutionEdges"] == ["UI_API", "API_REPO", "REPO_DB"]
    for alternative in proof["alternativeSolutions"]:
        assert simulate(p["mechanics"], alternative)["ok"]


@pytest.mark.parametrize("mutate", [
    lambda m: m["edges"][0].update(target="UI"),
    lambda m: m["edges"][1].update(source="UI", target="API"),
    lambda m: m["edges"][1].update(id="UI_API"),
    lambda m: m["nodes"][1].update(id="UI"),
    lambda m: m["connectionRules"][0]["allowed"][0].update(sourceKind="missing"),
    lambda m: m["connectionRules"][1].update(min=3, max=1),
    lambda m: m["connectionRules"][1].update(max=7),
    lambda m: m["goals"][0].update(source="DB", target="DB"),
    lambda m: m["edges"].extend([dict(m["edges"][0])] * 2),
])
def test_reject_invalid_graph_and_unbounded_search(mutate):
    p = puzzle()
    mutate(p["mechanics"])
    with pytest.raises(ValueError, match="REFERENCE_ERROR|SCHEMA_ERROR"):
        validate(p["mechanics"], {r["id"] for r in p["knowledge"]["requiredRules"]})


@pytest.mark.parametrize("state", [None, 3, {}, "UI_API", ["missing"], ["UI_API", "UI_API"], [[]]])
def test_invalid_serialized_graph_is_rejected_by_both_simulators(state):
    m = puzzle()["mechanics"]
    with pytest.raises(ValueError, match="STATE_ERROR"):
        simulate(m, state)
    node(r"""
const assert = require('node:assert/strict');
const {nodeConnectResult} = require('./mindcrafted/engine/world/node-connect.js');
const {mechanics, state} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
assert.throws(() => nodeConnectResult(mechanics, state), /STATE_ERROR/);
""", {"mechanics": m, "state": state})


def test_rejects_decorative_rule_even_when_the_graph_has_solutions():
    p = puzzle()
    p["mechanics"]["connectionRules"].append({"kind": "acyclic", "ruleId": "decorative"})
    p["knowledge"]["requiredRules"].append({"id": "decorative"})
    with pytest.raises(ValueError, match="EDUCATIONAL_COUPLING_ERROR.*prescindible decorative"):
        solve(p)


def test_rejects_trivially_random_configuration_with_real_rule_and_goal():
    p = {"id": "trivial", "knowledge": {"requiredRules": [{"id": "roles"}, {"id": "path"}]},
         "mechanics": {"archetype": "node_connect", "schemaVersion": 1,
            "nodes": [{"id": n, "label": n, "kind": n} for n in "ABC"],
            "edges": [{"id": a+b, "source": a, "target": b} for a, b in [("A", "B"), ("B", "C"), ("A", "C")]],
            "connectionRules": [{"kind": "compatible", "ruleId": "roles", "allowed": [
                {"sourceKind": "A", "targetKind": "B"}, {"sourceKind": "B", "targetKind": "C"}]}],
            "goals": [{"source": "A", "target": "B", "ruleId": "path"}]}}
    with pytest.raises(ValueError, match="RANDOM_SUCCESS_ERROR.*0.2500"):
        solve(p)


def test_acyclic_incoming_degree_and_direction_match_for_every_graph():
    p = puzzle()
    m = p["mechanics"]
    m["connectionRules"][0]["allowed"].append({"sourceKind": "repositorio", "targetKind": "servicio"})
    m["connectionRules"].extend([
        {"kind": "acyclic", "ruleId": "no_cycle"},
        {"kind": "degree", "node": "REPO", "direction": "in", "min": 1, "max": 1, "ruleId": "one_dependency"}])
    p["knowledge"]["requiredRules"].extend([{"id": "no_cycle"}, {"id": "one_dependency"}])
    assert solve(p)["solutionCount"] > 1
    cyclic = simulate(m, ["UI_API", "API_REPO", "REPO_API", "REPO_DB"])
    assert cyclic["cycleNodes"] == ["API", "REPO"]  # Downstream DB is not part of the cycle.
    assert not cyclic["ok"] and not cyclic["rules"]["no_cycle"]
    overloaded = simulate(m, ["UI_API", "API_REPO", "ALT_REPO", "REPO_DB"])
    assert overloaded["degreeErrors"] == ["REPO"]
    cases = [[e["id"] for e, selected in zip(m["edges"], mask) if selected]
             for mask in product((False, True), repeat=len(m["edges"]))]
    actual = node(r"""
const {nodeConnectResult} = require('./mindcrafted/engine/world/node-connect.js');
const {mechanics, cases} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(ids => nodeConnectResult(mechanics, ids))));
""", {"mechanics": m, "cases": cases})
    assert actual == [simulate(m, ids) for ids in cases]
