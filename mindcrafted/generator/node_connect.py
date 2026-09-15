"""Bounded directed-graph archetype: validate, simulate and prove solutions."""
from itertools import product
import random

from .world_schema import NodeConnect

RANDOM_SEED = 20260914
RANDOM_TRIALS = 256


def validate(mechanics, rule_ids):
    """Schema plus references; source quotes are checked by world.validate_mechanics."""
    try:
        NodeConnect.model_validate(mechanics)
    except ValueError as error:
        raise ValueError(f"SCHEMA_ERROR node_connect: {error}") from error

    def index(items, label):
        ids = [item["id"] for item in items]
        if len(ids) != len(set(ids)) or set(ids) & {"constructor", "prototype", "__proto__"}:
            raise ValueError(f"REFERENCE_ERROR node_connect: IDs duplicados o reservados en {label}")
        return {item["id"]: item for item in items}

    nodes = index(mechanics["nodes"], "nodes")
    index(mechanics["edges"], "edges")
    kinds = {node["kind"] for node in nodes.values()}
    pairs = set()
    for edge in mechanics["edges"]:
        pair = edge["source"], edge["target"]
        if pair in pairs or pair[0] == pair[1] or any(n not in nodes for n in pair):
            raise ValueError(f"REFERENCE_ERROR node_connect: enlace inválido {edge['id']}")
        pairs.add(pair)
    references, compatible = set(), []
    for rule in mechanics["connectionRules"]:
        references.add(rule["ruleId"])
        if rule["kind"] == "compatible":
            allowed = [(pair["sourceKind"], pair["targetKind"]) for pair in rule["allowed"]]
            if len(allowed) != len(set(allowed)) or any(a not in kinds or b not in kinds for a, b in allowed):
                raise ValueError(f"REFERENCE_ERROR node_connect: tipos inválidos en {rule['ruleId']}")
            compatible.append(set(allowed))
        elif rule["kind"] == "degree":
            if rule["node"] not in nodes or rule["min"] > rule["max"] or rule["max"] > len(nodes) - 1:
                raise ValueError(f"REFERENCE_ERROR node_connect: grado inválido en {rule['ruleId']}")
    for goal in mechanics["goals"]:
        references.add(goal["ruleId"])
        if goal["source"] not in nodes or goal["target"] not in nodes or goal["source"] == goal["target"]:
            raise ValueError(f"REFERENCE_ERROR node_connect: meta inválida en {goal['ruleId']}")
    if references != set(rule_ids):
        raise ValueError("REFERENCE_ERROR node_connect: cada restricción/meta necesita una requiredRule y viceversa")
    if not compatible or not any(
            (nodes[e["source"]]["kind"], nodes[e["target"]]["kind"]) not in allowed
            for allowed in compatible for e in mechanics["edges"]):
        raise ValueError("EDUCATIONAL_COUPLING_ERROR node_connect: la compatibilidad debe discriminar enlaces físicos")


def simulate(mechanics, connections, ignored_rule=None):
    """Pure arbitration. Connections are edge IDs; goal paths respect direction."""
    edge_ids = {edge["id"] for edge in mechanics["edges"]}
    if (not isinstance(connections, list) or any(not isinstance(edge, str) for edge in connections)
            or len(set(connections)) != len(connections) or not set(connections) <= edge_ids):
        raise ValueError("STATE_ERROR node_connect: conexiones desconocidas o duplicadas")
    selected = set(connections)
    active = [edge for edge in mechanics["edges"] if edge["id"] in selected]
    nodes = {node["id"]: node for node in mechanics["nodes"]}
    adjacency = {node: [] for node in nodes}
    for edge in active:
        adjacency[edge["source"]].append(edge["target"])

    def reachable(start, target):
        queue, seen = list(adjacency[start]), set()
        while queue:
            current = queue.pop()
            if current == target:
                return True
            if current not in seen:
                seen.add(current)
                queue.extend(adjacency[current])
        return False

    rules = {rule["ruleId"]: True for rule in mechanics["connectionRules"] + mechanics["goals"]}
    invalid, degree_errors, cycles, unreachable = set(), set(), set(), []
    for rule in mechanics["connectionRules"]:
        if rule["ruleId"] == ignored_rule:
            continue
        if rule["kind"] == "compatible":
            allowed = {(pair["sourceKind"], pair["targetKind"]) for pair in rule["allowed"]}
            wrong = {edge["id"] for edge in active if (nodes[edge["source"]]["kind"], nodes[edge["target"]]["kind"]) not in allowed}
            if wrong:
                invalid.update(wrong)
                rules[rule["ruleId"]] = False
        elif rule["kind"] == "degree":
            count = sum(edge["target" if rule["direction"] == "in" else "source"] == rule["node"] for edge in active)
            if not rule["min"] <= count <= rule["max"]:
                degree_errors.add(rule["node"])
                rules[rule["ruleId"]] = False
        elif rule["kind"] == "acyclic":
            found = {node for node in nodes if reachable(node, node)}
            if found:
                cycles.update(found)
                rules[rule["ruleId"]] = False
    for index, goal in enumerate(mechanics["goals"]):
        if goal["ruleId"] != ignored_rule and not reachable(goal["source"], goal["target"]):
            unreachable.append(index)
            rules[goal["ruleId"]] = False
    return {"ok": bool(active) and all(rules.values()), "rules": rules,
            "connections": [edge["id"] for edge in active], "invalidEdges": sorted(invalid),
            "unreachable": unreachable, "degreeErrors": sorted(degree_errors), "cycleNodes": sorted(cycles)}


def solve(puzzle):
    """Exhaust all <=4096 graphs; prove multiplicity and causal educational rules."""
    mechanics = puzzle["mechanics"]
    rule_ids = {rule["id"] for rule in puzzle["knowledge"]["requiredRules"]}
    validate(mechanics, rule_ids)
    edges = mechanics["edges"]
    candidates = [[edge["id"] for edge, selected in zip(edges, mask) if selected]
                  for mask in product((False, True), repeat=len(edges))]
    valid, invalid = [], []
    for connections in candidates:
        (valid if simulate(mechanics, connections)["ok"] else invalid).append(connections)
    if not valid:
        raise ValueError(f"UNSOLVABLE node_connect {puzzle.get('id', '')}: ningún grafo satisface las reglas y metas")
    if [edge["id"] for edge in edges] in valid:
        raise ValueError("EDUCATIONAL_COUPLING_ERROR node_connect: conectar todos los enlaces resuelve trivialmente")
    for rule in sorted(rule_ids):
        if not any(simulate(mechanics, candidate, ignored_rule=rule)["ok"] for candidate in invalid):
            raise ValueError(f"EDUCATIONAL_COUPLING_ERROR node_connect: regla prescindible {rule}")
    chance = len(valid) / len(candidates)
    difficulty = puzzle.get("difficulty", {})
    if chance > difficulty.get("randomSuccessProbabilityMax", .1):
        raise ValueError(f"RANDOM_SUCCESS_ERROR node_connect: {chance:.4f} de configuraciones resuelven")
    order = {edge["id"]: i for i, edge in enumerate(edges)}
    valid.sort(key=lambda ids: (len(ids), [order[edge] for edge in ids]))
    solution = valid[0]
    actions = []
    for edge_id in solution:
        edge = edges[order[edge_id]]
        actions.extend({"type": "control", "controlId": edge[key]} for key in ("source", "target"))
    actions.append({"type": "submit"})
    if difficulty and not difficulty["minSolutionSteps"] <= len(actions) <= difficulty["maxSolutionSteps"]:
        raise ValueError("DIFFICULTY_ERROR node_connect: solución fuera del límite de pasos")
    rng = random.Random(RANDOM_SEED)
    random_wins = sum(simulate(mechanics, [e["id"] for e in edges if rng.getrandbits(1)])["ok"] for _ in range(RANDOM_TRIALS))
    return {"actions": actions, "steps": len(actions), "solutionEdges": solution,
            "solutionCount": len(valid), "alternativeSolutions": valid[1:4], "evaluatedStates": len(candidates),
            "randomSuccessProbability": chance, "randomSuccessRate": random_wins / RANDOM_TRIALS,
            "randomTrials": RANDOM_TRIALS, "randomSeed": RANDOM_SEED}
