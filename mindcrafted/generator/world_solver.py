"""Bounded deterministic solvers; no generated code or LLM in arbitration."""

from collections import deque
from itertools import permutations, product
from math import prod, perm

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def sequence_ok(mechanics, sequence, ignored_rule=None):
    if set(sequence) != {s["id"] for s in mechanics["switches"]}:
        return False
    return all(sequence.index(c["before"]) < sequence.index(c["after"])
               for c in mechanics["constraints"] if c["ruleId"] != ignored_rule)


def route_options(mechanics):
    options = {}
    for edge in mechanics["edges"]:
        options.setdefault(edge["source"], []).append(edge["target"])
    return options


def network_result(mechanics, routes, ignored_rule=None):
    nodes = {n["id"]: n for n in mechanics["nodes"]}
    edges = {(e["source"], e["target"]) for e in mechanics["edges"]}
    loads = {key: 0 for key in nodes}
    delivered = 0
    for packet in mechanics["packets"]:
        current, seen = packet["source"], set()
        while current in nodes and current not in seen:
            seen.add(current)
            loads[current] += packet["amount"]
            if current == packet["target"]:
                delivered += 1
                break
            target = routes.get(current)
            if (current, target) not in edges:
                break
            current = target
        else:
            current = None
        if current != packet["target"] and packet["ruleId"] != ignored_rule:
            return {"ok": False, "loads": loads, "delivered": delivered, "reason": "delivery"}
    congested = [key for key, load in loads.items()
                 if load > nodes[key]["capacity"] and nodes[key]["ruleId"] != ignored_rule]
    return {"ok": not congested, "loads": loads, "delivered": delivered,
            "reason": "capacity" if congested else "ok"}


def blocks_ok(mechanics, positions, ignored_rule=None):
    goals = {(g["x"], g["y"]): g for g in mechanics["goals"]}
    return all(pos in goals and (block["kind"] in goals[pos]["accepts"]
               or block["ruleId"] == ignored_rule)
               for block, pos in zip(mechanics["blocks"], positions))


def solve_blocks(mechanics, budget=180000):
    board = mechanics["board"]
    free = {(x, y) for y, row in enumerate(board) for x, tile in enumerate(row) if tile == "."}
    initial = (tuple(mechanics["spawn"][k] for k in ("x", "y")),
               tuple((b["x"], b["y"]) for b in mechanics["blocks"]))
    queue, parents = deque([initial]), {initial: None}
    finish = None
    while queue:
        state = queue.popleft()
        player, blocks = state
        if blocks_ok(mechanics, blocks):
            finish = state
            break
        for direction, (dx, dy) in DIRECTIONS.items():
            dest = (player[0] + dx, player[1] + dy)
            if dest not in free:
                continue
            next_blocks = list(blocks)
            if dest in blocks:
                target = (dest[0] + dx, dest[1] + dy)
                if target not in free or target in blocks:
                    continue
                next_blocks[blocks.index(dest)] = target
            nxt = (dest, tuple(next_blocks))
            if nxt not in parents:
                if len(parents) >= budget:
                    raise ValueError("push_blocks excede el presupuesto del solver; simplifica el tablero")
                parents[nxt] = (state, direction)
                queue.append(nxt)
    if finish is None:
        raise ValueError("push_blocks no tiene solución")
    path = []
    while parents[finish] is not None:
        finish, direction = parents[finish]
        path.append(direction)
    return [{"type": "move", "direction": d} for d in reversed(path)]


def solve_puzzle(puzzle):
    m = puzzle["mechanics"]
    if m["archetype"] == "node_connect":
        from .node_connect import solve
        return solve(puzzle)
    if m["archetype"] == "resource_balance":
        from .resource_balance import solve
        return solve(puzzle)
    if m["archetype"] == "machine_configuration":
        from .machine_configuration import solve
        return solve(puzzle)
    rules = {r["id"] for r in puzzle["knowledge"]["requiredRules"]}
    kind = m["archetype"]
    if kind == "switch_sequence":
        candidates = list(permutations(s["id"] for s in m["switches"]))
        valid = [s for s in candidates if sequence_ok(m, s)]
        if not valid:
            raise ValueError("La secuencia es cíclica o imposible")
        for rule in rules:
            if not any(sequence_ok(m, s, rule) and not sequence_ok(m, s) for s in candidates):
                raise ValueError(f"Regla educativa prescindible: {rule}")
        actions = [{"type": "control", "controlId": s} for s in valid[0]]
        chance = len(valid) / len(candidates)
    elif kind == "route_network":
        options = route_options(m)
        count = prod(len(v) for v in options.values())
        if count > 4096:
            raise ValueError("La red excede 4096 configuraciones")
        candidates = [dict(zip(options, values)) for values in product(*options.values())]
        valid = [r for r in candidates if network_result(m, r)["ok"]]
        if not valid:
            raise ValueError("La red no entrega los paquetes sin congestión")
        for rule in rules:
            if not any(network_result(m, r, rule)["ok"] and not network_result(m, r)["ok"] for r in candidates):
                raise ValueError(f"Regla educativa prescindible: {rule}")
        actions = []
        for node, target in valid[0].items():
            for _ in range(options[node].index(target) + 1):
                actions.append({"type": "control", "controlId": node})
        actions.append({"type": "submit"})
        chance = len(valid) / count
    else:
        goals = [(g["x"], g["y"]) for g in m["goals"]]
        candidates = list(permutations(goals, len(m["blocks"])))
        valid = [s for s in candidates if blocks_ok(m, s)]
        for rule in rules:
            if not any(blocks_ok(m, s, rule) and not blocks_ok(m, s) for s in candidates):
                raise ValueError(f"Regla educativa prescindible: {rule}")
        actions = solve_blocks(m)
        chance = len(valid) / max(1, perm(len(goals), len(m["blocks"])))
    if not actions:
        raise ValueError("El puzzle comienza resuelto")
    if chance > puzzle.get("difficulty", {}).get("randomSuccessProbabilityMax", 0.1):
        raise ValueError(f"Éxito aleatorio demasiado probable: {chance:.3f}")
    difficulty = puzzle.get("difficulty")
    if difficulty and not difficulty["minSolutionSteps"] <= len(actions) <= difficulty["maxSolutionSteps"]:
        raise ValueError("La solución está fuera del límite de pasos")
    return {"actions": actions, "steps": len(actions), "randomSuccessProbability": chance}
