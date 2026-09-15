"""Bounded machine configuration: data predicates, pure arbitration, causal proof."""
import re

from . import finite_puzzle as finite
from .world_schema import MachineConfiguration


def eligibility(source):
    """Local signals only; does not select another mechanic or invent relations."""
    facts = {" ".join(s.split()).casefold() for s in re.split(r"[\n.;]+", source) if len(s.strip()) >= 15}
    related = [s for s in facts if re.search(r"configur|component|parámetr|parameter|modo|mode|módulo|module|opci[oó]n|estado|state", s)
               and re.search(r"requiere|necesita|depende|incompatible|no puede|compatible|debe|permite|require|depend|must|cannot", s)]
    return {"status": "PASS" if len(related) >= 2 else "SOURCE_TOO_WEAK_FOR_MACHINE_CONFIGURATION",
            "relationshipCount": len(related)}


def domains(m):
    result = {s["id"]: [None] + s["components"] for s in m["slots"]}
    for parameter in m["parameters"]:
        values = [v["id"] for v in parameter["values"]]
        start = values.index(parameter["initial"])
        result[parameter["id"]] = values[start:] + values[:start]
    return result


def validate(m, rule_ids):
    try:
        MachineConfiguration.model_validate(m)
    except ValueError as error:
        raise ValueError(f"SCHEMA_ERROR machine_configuration: {error}") from error
    finite.index([m["machine"]] + m["components"] + m["slots"] + m["parameters"], "machine/components/controls")
    component_ids = {c["id"] for c in m["components"]}
    used = set()
    for slot in m["slots"]:
        if len(set(slot["components"])) != len(slot["components"]) or not set(slot["components"]) <= component_ids:
            raise ValueError(f"REFERENCE_ERROR: catálogo de ranura inválido {slot['id']}")
        used.update(slot["components"])
    if used != component_ids:
        raise ValueError("REFERENCE_ERROR: componente sin ranura física")
    parameters = {p["id"]: p for p in m["parameters"]}
    for p in parameters.values():
        values = finite.index(p["values"], p["id"])
        if p["initial"] not in values:
            raise ValueError(f"REFERENCE_ERROR: valor inicial inexistente {p['id']}")
    choices = domains(m)
    finite.bounded(choices)

    referenced_controls, coupled = set(), False

    def condition(c):
        if c["control"] not in choices or len(c["values"]) != len(set(c["values"])) or not set(c["values"]) <= set(choices[c["control"]]):
            raise ValueError(f"REFERENCE_ERROR: condición inválida {c['control']}")
        referenced_controls.add(c["control"])

    references = set()
    for rule in m["configurationRules"] + m["goals"]:
        references.add(rule["ruleId"])
        kind = rule["kind"]
        if kind == "required":
            condition(rule["condition"])
        elif kind in ("dependency", "exclusion"):
            keys = ("when", "then") if kind == "dependency" else ("left", "right")
            for key in keys:
                condition(rule[key])
            coupled |= rule[keys[0]]["control"] != rule[keys[1]]["control"]
        elif kind == "range":
            if (rule["control"] not in parameters or rule["min"] > rule["max"] or
                    any(v["quantity"] is None for v in parameters[rule["control"]]["values"])):
                raise ValueError("REFERENCE_ERROR: rango necesita un parámetro cuantitativo y límites ordenados")
            referenced_controls.add(rule["control"])
        else:
            controls = [t["control"] for t in rule["terms"]]
            if len(controls) != len(set(controls)) or not set(controls) <= set(choices):
                raise ValueError("REFERENCE_ERROR: términos de capacidad duplicados o inexistentes")
            referenced_controls.update(controls)
            coupled |= len(controls) >= 2
            for term in rule["terms"]:
                costs = [c["value"] for c in term["costs"]]
                if len(costs) != len(set(costs)) or set(costs) != set(choices[term["control"]]) - {None}:
                    raise ValueError("REFERENCE_ERROR: capacidad necesita coste explícito de cada opción")
    if references != set(rule_ids):
        raise ValueError("REFERENCE_ERROR: cada restricción/meta necesita requiredRule y viceversa")
    if referenced_controls != set(choices) or not coupled:
        raise ValueError("EDUCATIONAL_COUPLING_ERROR: todos los controles deben aplicar reglas y existir relaciones entre controles")
    for tradeoff in m.get("tradeoffs", []):
        condition({"control": tradeoff["control"], "values": tradeoff["preferredValues"]})


def initial(m):
    return finite.initial(domains(m))


def transition(m, state, action):
    return finite.transition(domains(m), state, action)


def simulate(m, state, ignored_rule=None):
    """Invalid configurations stay editable. Only explicit submit may award success."""
    finite.check_state(domains(m), state)
    rules = {r["ruleId"]: True for r in m["configurationRules"] + m["goals"]}
    failures, affected, capacities = [], set(), []
    def holds(condition):
        return state[condition["control"]] in condition["values"]
    for rule in m["configurationRules"] + m["goals"]:
        if rule["ruleId"] == ignored_rule:
            continue
        kind = rule["kind"]
        if kind == "required":
            ok, controls = holds(rule["condition"]), [rule["condition"]["control"]]
        elif kind == "dependency":
            ok = not holds(rule["when"]) or holds(rule["then"])
            controls = [rule["when"]["control"], rule["then"]["control"]]
        elif kind == "exclusion":
            ok = not (holds(rule["left"]) and holds(rule["right"]))
            controls = [rule["left"]["control"], rule["right"]["control"]]
        elif kind == "range":
            parameter = next(p for p in m["parameters"] if p["id"] == rule["control"])
            quantity = next(v["quantity"] for v in parameter["values"] if v["id"] == state[parameter["id"]])
            ok, controls = rule["min"] <= quantity <= rule["max"], [parameter["id"]]
        else:
            total = sum(next((c["amount"] for c in t["costs"] if c["value"] == state[t["control"]]), 0) for t in rule["terms"])
            ok, controls = total <= rule["max"], [t["control"] for t in rule["terms"]]
            capacities.append({"ruleId": rule["ruleId"], "load": total, "max": rule["max"], "unit": rule["unit"]})
        rules[rule["ruleId"]] &= ok
        if not ok:
            affected.update(controls)
            failures.append({"kind": kind, "ruleId": rule["ruleId"], "controls": controls})
    return {"ok": all(rules.values()), "rules": rules, "configuration": dict(state),
            "failures": failures, "affectedControls": sorted(affected), "capacities": capacities}


def solve(puzzle):
    m = puzzle["mechanics"]
    validate(m, {r["id"] for r in puzzle["knowledge"]["requiredRules"]})
    proof = finite.prove(puzzle, domains(m), lambda state, ignored=None: simulate(m, state, ignored))
    # Preferences explain compromises; they never change correctness or rewards.
    proof["tradeoffs"] = [{**t, "preferred": proof["solution"][t["control"]] in t["preferredValues"]} for t in m.get("tradeoffs", [])]
    return proof
