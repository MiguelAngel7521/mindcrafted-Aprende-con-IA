"""Small finite-domain proofs shared by deterministic selector mechanisms."""
from itertools import product
from math import prod
import random

MAX_STATES = 4096
RANDOM_SEED = 20260915
RANDOM_TRIALS = 256


def index(items, label):
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)) or set(ids) & {"constructor", "prototype", "__proto__"}:
        raise ValueError(f"REFERENCE_ERROR: IDs duplicados o reservados en {label}")
    return {item["id"]: item for item in items}


def bounded(domains):
    if prod(map(len, domains.values())) > MAX_STATES:
        raise ValueError(f"SOLUTION_BOUNDS_ERROR: máximo {MAX_STATES} estados")


def initial(domains):
    return {key: values[0] for key, values in domains.items()}


def check_state(domains, state):
    if (not isinstance(state, dict) or set(state) != set(domains)
            or any(not any(type(value) is type(option) and value == option for option in domains[key])
                   for key, value in state.items())):
        raise ValueError("STATE_ERROR: configuración incompleta, desconocida o fuera del dominio")


def transition(domains, state, action):
    check_state(domains, state)
    if action == {"type": "reset"}:
        return initial(domains)
    if action == {"type": "submit"}:
        return dict(state)
    if (not isinstance(action, dict) or set(action) != {"type", "controlId"}
            or action["type"] != "control" or not isinstance(action["controlId"], str)
            or action["controlId"] not in domains):
        raise ValueError("ACTION_ERROR: control inexistente o acción no declarada")
    control = action["controlId"]
    choices = domains[control]
    return dict(state, **{control: choices[(choices.index(state[control]) + 1) % len(choices)]})


def prove(puzzle, domains, simulate):
    """Enumerate all states and demonstrate a counterexample for each removed rule."""
    bounded(domains)
    candidates = [dict(zip(domains, values)) for values in product(*domains.values())]
    valid, witnesses = [], {}
    rule_ids = {r["id"] for r in puzzle["knowledge"]["requiredRules"]}
    for state in candidates:
        result = simulate(state)
        if result["ok"]:
            valid.append(state)
        else:
            failed = [key for key, ok in result["rules"].items() if not ok]
            if len(failed) == 1 and simulate(state, failed[0])["ok"]:
                witnesses.setdefault(failed[0], state)
    kind = puzzle["mechanics"]["archetype"]
    if not valid:
        raise ValueError(f"UNSOLVABLE {kind}: no existe configuración válida")
    if initial(domains) in valid:
        raise ValueError(f"EDUCATIONAL_COUPLING_ERROR {kind}: comienza resuelto")
    if rule_ids - witnesses.keys():
        raise ValueError(f"EDUCATIONAL_COUPLING_ERROR {kind}: reglas prescindibles {sorted(rule_ids - witnesses.keys())}")
    # Empty slots/unassigned loads must not artificially depress random success.
    complete = [s for s in candidates if all(v is not None for v in s.values())]
    chance = max(len(valid) / len(candidates), sum(s in valid for s in complete) / max(1, len(complete)))
    if chance > puzzle.get("difficulty", {}).get("randomSuccessProbabilityMax", .1):
        raise ValueError(f"RANDOM_SUCCESS_ERROR {kind}: {chance:.4f}")
    cost = lambda s: sum(domains[key].index(value) for key, value in s.items())
    valid.sort(key=cost)
    solution = valid[0]
    actions = [{"type": "control", "controlId": key} for key, value in solution.items()
               for _ in range(domains[key].index(value))] + [{"type": "submit"}]
    difficulty = puzzle.get("difficulty")
    if difficulty and not difficulty["minSolutionSteps"] <= len(actions) <= difficulty["maxSolutionSteps"]:
        raise ValueError(f"DIFFICULTY_ERROR {kind}: solución fuera del límite de pasos")
    rng = random.Random(RANDOM_SEED)
    wins = sum(simulate({k: rng.choice(v) for k, v in domains.items()})["ok"] for _ in range(RANDOM_TRIALS))
    return {"actions": actions, "steps": len(actions), "solution": solution, "solutionCount": len(valid),
            "alternativeSolutions": valid[1:4], "evaluatedStates": len(candidates),
            "minChanges": min(sum(s[k] != v[0] for k, v in domains.items()) for s in valid),
            "ablationWitnesses": witnesses, "recoverable": True,
            "randomSuccessProbability": chance, "randomSuccessRate": wins / RANDOM_TRIALS,
            "randomTrials": RANDOM_TRIALS, "randomSeed": RANDOM_SEED}
