"""Compile authored/AI blueprints into persistent, deterministic worlds."""

from collections import deque
from copy import deepcopy
import hashlib
import json

from jsonschema import Draft202012Validator

from .world_schema import BLUEPRINT_SCHEMA, WORLD_SCHEMA
from .world_solver import DIRECTIONS, route_options, solve_puzzle


def schema_check(value, schema):
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise ValueError("; ".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors[:6]))


def unique(items, label):
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids) or any(i in {"constructor", "prototype", "__proto__"} for i in ids):
        raise ValueError(f"IDs duplicados o reservados en {label}")
    return {item["id"]: item for item in items}


def configuration_controls(mechanics):
    groups = (("loads", "resource_load"), ("targets", "resource_target")) if mechanics["archetype"] == "resource_balance" else (("slots", "machine_slot"), ("parameters", "machine_parameter"))
    return [(control, kind) for group, kind in groups for control in mechanics[group]]


def compile_puzzle_spec(blueprint, region_id, index, difficulty="normal", prerequisites=()):
    puzzle = deepcopy(blueprint)
    pid = puzzle["id"]
    solution = solve_puzzle(puzzle)
    puzzle.update(runtime="world", archetype=puzzle["mechanics"]["archetype"], mandatory=True, resettable=True,
                  role=puzzle.get("role", "challenge"), prerequisites=list(prerequisites),
                  world={"region": region_id, "anchorEntity": f"{pid}_console", "offset": {"x": index * 22 + 10, "y": 4}},
                  success={"setFlags": [f"{pid}_restored"], "xp": 200 if puzzle.get("role") == "boss" else 75, "openEntity": f"{pid}_gate", "dialogue": f"{pid}_after"},
                  failure={"autoReset": puzzle["mechanics"]["archetype"] not in ("resource_balance", "machine_configuration"), "hintAfterAttempts": 3, "worldEffect": "power_loss"},
                  difficulty={"level": difficulty, "minSolutionSteps": max(6 if difficulty == "hard" or puzzle.get("role") == "boss" else 1, solution["steps"]), "maxSolutionSteps": max(12, solution["steps"] * 2),
                              "randomSuccessProbabilityMax": 0.1})
    return puzzle


def compile_world(blueprint, source, world_id="learning_world", *, difficulty="normal", prior_skills=()):
    schema_check(blueprint, BLUEPRINT_SCHEMA)
    unique(blueprint["puzzles"], "blueprint")
    # Validate references before invoking combinatorial solvers.
    for puzzle in blueprint["puzzles"]:
        validate_mechanics(puzzle, source)
    region_id = "main_region"
    puzzles = [compile_puzzle_spec(p, region_id, i, difficulty, [q["id"] for q in blueprint["puzzles"][:i]]) for i, p in enumerate(blueprint["puzzles"])]
    width, height = len(puzzles) * 22 + 2, 19
    tiles = [["#" if x in (0, width - 1) or y in (0, height - 1) else "."
              for x in range(width)] for y in range(height)]
    entities, dialogues, quests = [], [], []
    for i, puzzle in enumerate(puzzles):
        pid, base = puzzle["id"], i * 22
        for y in range(1, height - 1):
            tiles[y][base + 21] = "." if y == 9 else "#"
        entities.extend([
            {"id": f"{pid}_mentor", "type": "npc", "label": "Luna", "x": base + 4, "y": 9,
             "puzzleId": pid, "dialogueId": f"{pid}_intro"},
            {"id": f"{pid}_console", "type": "console", "label": "Control de energía", "x": base + 7, "y": 9, "puzzleId": pid},
            {"id": f"{pid}_gate", "type": "door", "label": "Compuerta del distrito", "x": base + 21, "y": 9,
             "puzzleId": pid, "requiresFlag": f"{pid}_restored"},
        ])
        m = puzzle["mechanics"]
        if puzzle["archetype"] == "push_blocks":
            ox, oy = (puzzle["world"]["offset"][axis] for axis in ("x", "y"))
            for y, row in enumerate(m["board"]):
                for x, tile in enumerate(row):
                    tiles[oy + y][ox + x] = tile
            for goal in m["goals"]:
                entities.append({"id": f"{pid}_{goal['id']}", "type": "goal", "label": goal["label"],
                                 "x": ox + goal["x"], "y": oy + goal["y"], "puzzleId": pid, "controlId": goal["id"]})
        elif puzzle["archetype"] in ("resource_balance", "machine_configuration"):
            if puzzle["archetype"] == "machine_configuration":
                next(e for e in entities if e["id"] == f"{pid}_console")["label"] = m["machine"]["label"]
            for j, (control, kind) in enumerate(configuration_controls(m)):
                entities.append({"id": f"{pid}_{control['id']}", "type": kind,
                                 "label": control["label"], "x": base + 10 + j % 3 * 3, "y": 3 + j // 3 * 3,
                                 "puzzleId": pid, "controlId": control["id"]})
        else:
            controls = m["switches"] if puzzle["archetype"] == "switch_sequence" else m["nodes"]
            control_type = {"switch_sequence": "switch", "route_network": "router", "node_connect": "connection_node"}[puzzle["archetype"]]
            for j, control in enumerate(controls):
                entities.append({"id": f"{pid}_{control['id']}", "type": control_type,
                                 "label": control["label"], "x": base + 10 + j % 3 * 3, "y": 3 + j // 3 * 3,
                                 "puzzleId": pid, "controlId": control["id"]})
        quests.append({"id": f"{pid}_quest", "title": puzzle["objective"], "puzzleId": pid, "giver": f"{pid}_mentor"})
        dialogues.extend([
            {"id": f"{pid}_intro", "trigger": {"event": "entity.interacted", "entityId": f"{pid}_mentor"},
             "speaker": f"{pid}_mentor", "lines": [{"speaker": "Luna", "text": puzzle["introduction"]}],
             "onComplete": [{"type": "startQuest", "target": f"{pid}_quest"}]},
            {"id": f"{pid}_after", "trigger": {"event": "puzzle.solved", "puzzleId": pid},
             "speaker": f"{pid}_mentor", "lines": [{"speaker": "Luna", "text": puzzle["reflection"]}],
             "onComplete": [{"type": "setFlag", "target": f"{pid}_understood"}]},
        ])
    entities.append({"id": "region_exit", "type": "exit", "label": "Siguiente región", "x": width - 2, "y": 9})
    world = {"version": 2, "id": world_id, "title": blueprint["title"], "introduction": blueprint["introduction"],
             "priorSkills": sorted(set(prior_skills)),
             "player": {"controllable": True, "spawnRegion": region_id, "x": 2, "y": 9},
             "regions": [{"id": region_id, "title": blueprint["title"], "width": width, "height": height,
                          "tiles": ["".join(row) for row in tiles], "entities": entities}],
             "puzzles": puzzles, "dialogues": dialogues, "quests": quests}
    report = validate_world(world, source)
    if not report["ok"]:
        raise ValueError("; ".join(report["errors"]))
    return world


def validate_mechanics(puzzle, source):
    knowledge = puzzle["knowledge"]
    rules = unique(knowledge["requiredRules"], "requiredRules")
    normalized = " ".join(source.split()).casefold()
    for rule in rules.values():
        if not rule["evidence"].strip() or " ".join(rule["evidence"].split()).casefold() not in normalized:
            raise ValueError(f"La evidencia de {rule['id']} no aparece en el material")
    m = puzzle["mechanics"]
    references = []
    if m["archetype"] == "switch_sequence":
        switches = unique(m["switches"], "switches")
        for c in m["constraints"]:
            if c["before"] not in switches or c["after"] not in switches or c["before"] == c["after"]:
                raise ValueError("Secuencia con referencia inválida")
            references.append(c["ruleId"])
    elif m["archetype"] == "route_network":
        nodes = unique(m["nodes"], "nodes")
        unique(m["packets"], "packets")
        edges = [(e["source"], e["target"]) for e in m["edges"]]
        if len(set(edges)) != len(edges):
            raise ValueError("Cables duplicados")
        for edge in m["edges"] + m["packets"]:
            if edge["source"] not in nodes or edge["target"] not in nodes or edge["source"] == edge["target"]:
                raise ValueError("Red con referencia inválida")
        references = [n["ruleId"] for n in m["nodes"] + m["packets"]]
    elif m["archetype"] == "machine_configuration":
        from .machine_configuration import validate, eligibility
        source_report = eligibility(source)
        if source_report["status"] != "PASS":
            raise ValueError(source_report["status"])
        validate(m, set(rules))
        references = [r["ruleId"] for r in m["configurationRules"] + m["goals"]]
    elif m["archetype"] == "resource_balance":
        from .resource_balance import validate, eligibility
        source_report = eligibility(source)
        if source_report["status"] != "PASS":
            raise ValueError(source_report["status"])
        validate(m, set(rules))
        references = [r["ruleId"] for r in m["allocationRules"] + m["goals"]]
    elif m["archetype"] == "node_connect":
        from .node_connect import validate
        validate(m, set(rules))
        references = [r["ruleId"] for r in m["connectionRules"] + m["goals"]]
    else:
        unique(m["blocks"], "blocks")
        unique(m["goals"], "goals")
        board = m["board"]
        if any(len(row) != len(board[0]) for row in board):
            raise ValueError("Tablero irregular")
        for group in (m["blocks"], m["goals"]):
            if len({(p["x"], p["y"]) for p in group}) != len(group):
                raise ValueError("Bloques o destinos superpuestos")
        for p in m["blocks"] + m["goals"] + [m["spawn"]]:
            if p["y"] >= len(board) or p["x"] >= len(board[0]) or board[p["y"]][p["x"]] != ".":
                raise ValueError("Pieza fuera del suelo transitable")
        if (m["spawn"]["x"], m["spawn"]["y"]) in {(b["x"], b["y"]) for b in m["blocks"]}:
            raise ValueError("El jugador aparece encima de un bloque")
        references = [g["ruleId"] for g in m["goals"] + m["blocks"]]
    if set(references) != set(rules):
        raise ValueError("Cada requiredRule debe estar vinculada a una restricción ejecutable")


def validate_world(world, source):
    checks = {key: False for key in ("schema", "worldGraph", "solver", "educational")}
    errors, solutions = [], {}
    try:
        schema_check(world, WORLD_SCHEMA)
        checks["schema"] = True
        regions = unique(world["regions"], "regions")
        puzzles = unique(world["puzzles"], "puzzles")
        entities = unique([e for r in world["regions"] for e in r["entities"]], "entities")
        dialogues = unique(world["dialogues"], "dialogues")
        quests = unique(world["quests"], "quests")
        for region in regions.values():
            if len(region["tiles"]) != region["height"] or any(len(row) != region["width"] or set(row) - {".", "#"} for row in region["tiles"]):
                raise ValueError("Dimensiones del mapa inválidas")
            unique_positions = set()
            for entity in region["entities"]:
                pos = entity["x"], entity["y"]
                if pos in unique_positions or not 0 <= pos[0] < region["width"] or not 0 <= pos[1] < region["height"] or region["tiles"][pos[1]][pos[0]] != ".":
                    raise ValueError("Entidad superpuesta, en pared o fuera del mapa")
                unique_positions.add(pos)
                if entity.get("puzzleId") and entity["puzzleId"] not in puzzles:
                    raise ValueError("Entidad con puzzle inexistente")
                if entity.get("dialogueId") and entity["dialogueId"] not in dialogues:
                    raise ValueError("Entidad con diálogo inexistente")
                if entity["type"] != "exit" and entity.get("puzzleId") not in puzzles:
                    raise ValueError("Entidad interactiva sin puzzle")
                if entity["type"] == "npc" and entity.get("dialogueId") not in dialogues:
                    raise ValueError("NPC sin diálogo")
                if entity["type"] in ("switch", "router", "connection_node", "resource_load", "resource_target", "machine_slot", "machine_parameter", "goal"):
                    expected_type = {"switch_sequence": "switch", "route_network": "router", "push_blocks": "goal", "node_connect": "connection_node"}
                    archetype = puzzles[entity["puzzleId"]]["archetype"]
                    allowed = {"resource_load", "resource_target"} if archetype == "resource_balance" else {"machine_slot", "machine_parameter"} if archetype == "machine_configuration" else {expected_type[archetype]}
                    if entity["type"] not in allowed:
                        raise ValueError("Tipo de control incompatible con el puzzle")
        if world["player"]["spawnRegion"] not in regions:
            raise ValueError("Región de aparición inexistente")
        # v2 slice is one traversable region per chunk. Reject unsupported portals.
        if len(regions) != 1:
            raise ValueError("Esta versión requiere una región por paquete")
        learned_skills = set(world.get("priorSkills", []))
        preceding = set()
        for puzzle in puzzles.values():
            pid = puzzle["id"]
            if not set(puzzle.get("prerequisites", [])).issubset(preceding):
                raise ValueError("Prerrequisito de puzzle inexistente, futuro o cíclico")
            skills = {r["skill"] for r in puzzle["knowledge"]["requiredRules"]}
            if puzzle.get("role") == "boss":
                if not 2 <= len(skills) <= 4 or not skills.issubset(learned_skills):
                    raise ValueError("Un boss debe combinar de 2 a 4 habilidades aprendidas previamente")
                if pid != world["puzzles"][-1]["id"]:
                    raise ValueError("El boss debe cerrar la región")
            learned_skills.update(skills)
            preceding.add(pid)
            region = regions.get(puzzle["world"]["region"])
            if region is None or puzzle["archetype"] != puzzle["mechanics"]["archetype"]:
                raise ValueError("Región o arquetipo incoherente")
            anchor = entities.get(puzzle["world"]["anchorEntity"])
            door = entities.get(puzzle["success"]["openEntity"])
            if not anchor or anchor["type"] != "console" or anchor.get("puzzleId") != pid or anchor not in region["entities"]:
                raise ValueError("Anchor inexistente o ajeno al puzzle")
            if not door or door["type"] != "door" or door.get("puzzleId") != pid or door.get("requiresFlag") not in puzzle["success"]["setFlags"]:
                raise ValueError("La consecuencia no abre una puerta válida")
            after = dialogues.get(puzzle["success"]["dialogue"])
            if not after or after["trigger"] != {"event": "puzzle.solved", "puzzleId": pid}:
                raise ValueError("Diálogo de consecuencia inválido")
            if len([q for q in quests.values() if q["puzzleId"] == pid]) != 1:
                raise ValueError("Cada puzzle necesita una misión")
            controls = [e.get("controlId") for e in region["entities"] if e.get("puzzleId") == pid and e["type"] in ("switch", "router", "connection_node", "resource_load", "resource_target", "machine_slot", "machine_parameter", "goal")]
            m = puzzle["mechanics"]
            automatic_reset = puzzle["archetype"] not in ("resource_balance", "machine_configuration")
            if puzzle["failure"]["autoReset"] != automatic_reset:
                raise ValueError("WORLD_INTEGRATION_ERROR: recuperación incompatible con el archetype")
            if puzzle["archetype"] in ("resource_balance", "machine_configuration"):
                expected_types = {c["id"]: kind for c, kind in configuration_controls(m)}
                expected = list(expected_types)
                for entity in region["entities"]:
                    if entity.get("puzzleId") == pid and entity.get("controlId"):
                        if entity["type"] != expected_types.get(entity["controlId"]):
                            raise ValueError("WORLD_INTEGRATION_ERROR: tipo de control incorrecto")
            else:
                expected = [s["id"] for s in m.get("switches", m.get("nodes", m.get("goals", [])))]
            if sorted(controls) != sorted(expected):
                raise ValueError("Controles físicos incompletos")
            if puzzle["archetype"] == "push_blocks":
                ox, oy = (puzzle["world"]["offset"][axis] for axis in ("x", "y"))
                for y, row in enumerate(m["board"]):
                    if oy + y >= region["height"] or ox + len(row) > region["width"] or region["tiles"][oy + y][ox:ox + len(row)] != row:
                        raise ValueError("El tablero de bloques no coincide con el mapa")
                for goal in m["goals"]:
                    entity = next(e for e in region["entities"] if e.get("puzzleId") == pid and e.get("controlId") == goal["id"])
                    if (entity["x"], entity["y"]) != (ox + goal["x"], oy + goal["y"]):
                        raise ValueError("La meta física no coincide con el tablero")
                for point in m["blocks"] + [m["spawn"]]:
                    if any(e["x"] == ox + point["x"] and e["y"] == oy + point["y"] and e["type"] not in ("goal", "exit") for e in region["entities"]):
                        raise ValueError("El tablero contiene una entidad que bloquea sus piezas")
            validate_mechanics(puzzle, source)
            solutions[pid] = solve_puzzle(puzzle)
            if (puzzle["difficulty"].get("level") == "hard" or puzzle.get("role") == "boss") and solutions[pid]["steps"] < 6:
                raise ValueError("Un puzzle hard o boss necesita al menos seis acciones verificables")
        flags = {f for p in puzzles.values() for f in p["success"]["setFlags"]}
        for dialogue in dialogues.values():
            if dialogue["speaker"] not in entities or entities[dialogue["speaker"]]["type"] != "npc":
                raise ValueError("Emisor del diálogo inexistente")
            trigger = dialogue["trigger"]
            if trigger["event"] == "entity.interacted" and trigger.get("entityId") not in entities:
                raise ValueError("Trigger inexistente")
            if trigger["event"] == "puzzle.solved" and trigger.get("puzzleId") not in puzzles:
                raise ValueError("Trigger de puzzle inexistente")
            if trigger["event"] == "entity.interacted":
                npc = entities[trigger["entityId"]]
                if npc["type"] != "npc" or npc.get("dialogueId") != dialogue["id"] or dialogue["speaker"] != npc["id"]:
                    raise ValueError("El trigger de diálogo no corresponde a un NPC interactuable")
            elif puzzles[trigger["puzzleId"]]["success"]["dialogue"] != dialogue["id"]:
                raise ValueError("El trigger de éxito no es consumido por el puzzle")
            for effect in dialogue["onComplete"]:
                if effect["type"] == "startQuest" and effect["target"] not in quests:
                    raise ValueError("Misión inexistente")
                if effect["type"] == "setFlag" and effect["target"] in flags:
                    raise ValueError("Un diálogo no puede saltarse una compuerta educativa")
        for quest in quests.values():
            if quest["puzzleId"] not in puzzles or quest["giver"] not in entities:
                raise ValueError("Misión con referencia inválida")
            giver = entities[quest["giver"]]
            if giver["type"] != "npc" or giver.get("puzzleId") != quest["puzzleId"] or giver.get("dialogueId") not in dialogues:
                raise ValueError("La misión necesita un NPC y una conversación de inicio")
            intro = dialogues[giver["dialogueId"]]
            if intro["trigger"] != {"event": "entity.interacted", "entityId": giver["id"]}:
                raise ValueError("El NPC no corresponde al evento del diálogo")
        checks["solver"] = checks["educational"] = True
        walkthrough = build_walkthrough(world, solutions)
        checks["worldGraph"] = True
    except (ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        errors.append(str(error))
        walkthrough = []
    return {"ok": all(checks.values()), "checks": checks, "errors": errors,
            "solutions": solutions, "walkthrough": walkthrough}


def find_path(region, start, targets, obstacles):
    queue, parents = deque([start]), {start: None}
    finish = None
    while queue:
        current = queue.popleft()
        if current in targets:
            finish = current
            break
        for direction, (dx, dy) in DIRECTIONS.items():
            nxt = current[0] + dx, current[1] + dy
            x, y = nxt
            if nxt not in parents and nxt not in obstacles and 0 <= x < region["width"] and 0 <= y < region["height"] and region["tiles"][y][x] == ".":
                parents[nxt] = current, direction
                queue.append(nxt)
    if finish is None:
        raise ValueError("Softlock: objetivo o control inaccesible con las puertas actuales")
    end, path = finish, []
    while parents[finish] is not None:
        finish, direction = parents[finish]
        path.append({"type": "move", "direction": direction})
    return end, list(reversed(path))


def build_walkthrough(world, solutions):
    region = world["regions"][0]
    player = world["player"]["x"], world["player"]["y"]
    entities = {e["id"]: e for e in region["entities"]}
    obstacles = {(e["x"], e["y"]) for e in entities.values() if e["type"] not in ("goal", "exit")}
    blocks = {}
    for p in world["puzzles"]:
        if p["archetype"] == "push_blocks":
            offset = p["world"]["offset"]
            blocks[p["id"]] = [(b["x"] + offset["x"], b["y"] + offset["y"]) for b in p["mechanics"]["blocks"]]
    if player in obstacles or not 0 <= player[0] < region["width"] or not 0 <= player[1] < region["height"] or region["tiles"][player[1]][player[0]] != ".":
        raise ValueError("Spawn no transitable")
    trace = []

    def walk(targets):
        nonlocal player
        player, path = find_path(region, player, targets, obstacles | {b for group in blocks.values() for b in group})
        trace.extend(path)

    def interact(entity):
        walk({(entity["x"] + dx, entity["y"] + dy) for dx, dy in DIRECTIONS.values()})
        trace.append({"type": "interact", "entityId": entity["id"]})

    for p in world["puzzles"]:
        quest = next(q for q in world["quests"] if q["puzzleId"] == p["id"])
        giver = entities[quest["giver"]]
        intro = next(d for d in world["dialogues"] if d["id"] == giver.get("dialogueId"))
        if {"type": "startQuest", "target": quest["id"]} not in intro["onComplete"]:
            raise ValueError("La conversación no activa la misión")
        interact(giver)
        trace.extend({"type": "dialogue"} for _ in intro["lines"])
        if p["archetype"] in ("resource_balance", "machine_configuration"):
            for control in (e for e in entities.values() if e.get("puzzleId") == p["id"] and e.get("controlId")):
                find_path(region, player, {(control["x"] + dx, control["y"] + dy) for dx, dy in DIRECTIONS.values()},
                          obstacles | {b for group in blocks.values() for b in group})
        if p["archetype"] == "push_blocks":
            offset, m = p["world"]["offset"], p["mechanics"]
            walk({(m["spawn"]["x"] + offset["x"], m["spawn"]["y"] + offset["y"])})
        for action in solutions[p["id"]]["actions"]:
            if action["type"] == "control":
                interact(next(e for e in entities.values() if e.get("puzzleId") == p["id"] and e.get("controlId") == action["controlId"]))
            elif action["type"] == "submit":
                interact(entities[p["world"]["anchorEntity"]])
            else:
                dx, dy = DIRECTIONS[action["direction"]]
                player = player[0] + dx, player[1] + dy
                positions = blocks[p["id"]]
                if player in positions:
                    positions[positions.index(player)] = (player[0] + dx, player[1] + dy)
                trace.append(action)
        obstacles.discard((entities[p["success"]["openEntity"]]["x"], entities[p["success"]["openEntity"]]["y"]))
        after = next(d for d in world["dialogues"] if d["id"] == p["success"]["dialogue"])
        trace.extend({"type": "dialogue"} for _ in after["lines"])
    exits = [e for e in entities.values() if e["type"] == "exit"]
    if not exits:
        raise ValueError("Región sin salida")
    interact(exits[0])
    return trace


def world_hash(world):
    return hashlib.sha256(json.dumps(world, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
