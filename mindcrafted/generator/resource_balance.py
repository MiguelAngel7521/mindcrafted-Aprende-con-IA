"""Indivisible workloads, conceptual compatibility and aggregate resource budgets."""
import re

from . import finite_puzzle as finite
from .world_schema import ResourceBalance


def eligibility(source):
    facts = {" ".join(s.split()).casefold() for s in re.split(r"[\n.;]+", source) if len(s.strip()) >= 15}
    relations = [s for s in facts if re.search(r"carga|capacidad|recurso|presupuesto|load|capacity|budget", s)
                 and re.search(r"requiere|asign|super|necesita|consume|máximo|require|exceed|limit", s)]
    return {"status": "PASS" if len(relations) >= 2 else "SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE",
            "relationshipCount": len(relations)}


def domains(m):
    return {load["id"]: [None] + [t["id"] for t in m["targets"]] for load in m["loads"]}


def validate(m, rule_ids):
    try:
        ResourceBalance.model_validate(m)
    except ValueError as error:
        raise ValueError(f"SCHEMA_ERROR resource_balance: {error}") from error
    finite.index(m["loads"] + m["targets"], "loads/targets")
    targets = {t["id"] for t in m["targets"]}
    if len(m["loads"]) + len(targets) > 9:
        raise ValueError("SOLUTION_BOUNDS_ERROR: máximo nueve objetos de reparto")
    finite.bounded(domains(m))
    references, limited, kinds = set(), set(), set()
    for rule in m["allocationRules"] + m["goals"]:
        references.add(rule["ruleId"])
        kinds.add(rule["kind"])
        if rule["kind"] == "capacity":
            ids = [limit["target"] for limit in rule["limits"]]
            if len(ids) != len(set(ids)) or not set(ids) <= targets or any(l["min"] > l["max"] for l in rule["limits"]):
                raise ValueError("REFERENCE_ERROR: límites de capacidad inválidos")
            limited.update(ids)
        if rule["kind"] == "compatible":
            pairs = [(p["sourceKind"], p["targetKind"]) for p in rule["allowed"]]
            if len(pairs) != len(set(pairs)) or any(a not in {l["kind"] for l in m["loads"]} or b not in {t["kind"] for t in m["targets"]} for a, b in pairs):
                raise ValueError("REFERENCE_ERROR: tipos de recurso desconocidos o repetidos")
    if references != set(rule_ids) or limited != targets or not {"capacity", "compatible", "all_assigned"} <= kinds:
        raise ValueError("REFERENCE_ERROR: cada regla necesita evidencia y cada receptor capacidad/compatibilidad")


def initial(m):
    return finite.initial(domains(m))


def transition(m, state, action):
    return finite.transition(domains(m), state, action)


def simulate(m, state, ignored_rule=None):
    finite.check_state(domains(m), state)
    targets = {t["id"]: t for t in m["targets"]}
    loads = dict.fromkeys(targets, 0)
    for load in m["loads"]:
        if state[load["id"]] is not None:
            loads[state[load["id"]]] += load["amount"]
    rules = {r["ruleId"]: True for r in m["allocationRules"] + m["goals"]}
    incompatible, overloaded = set(), set()
    for rule in m["allocationRules"]:
        if rule["ruleId"] == ignored_rule:
            continue
        if rule["kind"] == "compatible":
            allowed = {(p["sourceKind"], p["targetKind"]) for p in rule["allowed"]}
            wrong = {l["id"] for l in m["loads"] if state[l["id"]] is not None and
                     (l["kind"], targets[state[l["id"]]]["kind"]) not in allowed}
        else:
            wrong = {l["target"] for l in rule["limits"] if not l["min"] <= loads[l["target"]] <= l["max"]}
        if wrong:
            rules[rule["ruleId"]] = False
            (incompatible if rule["kind"] == "compatible" else overloaded).update(wrong)
    for goal in m["goals"]:
        if goal["ruleId"] != ignored_rule:
            rules[goal["ruleId"]] &= all(value is not None for value in state.values())
    return {"ok": all(rules.values()), "rules": rules, "configuration": dict(state), "loads": loads,
            "incompatible": sorted(incompatible), "overloaded": sorted(overloaded)}


def solve(puzzle):
    m = puzzle["mechanics"]
    validate(m, {r["id"] for r in puzzle["knowledge"]["requiredRules"]})
    return finite.prove(puzzle, domains(m), lambda state, ignored=None: simulate(m, state, ignored))
