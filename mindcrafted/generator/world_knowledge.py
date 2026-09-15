"""Deterministic, source-traceable knowledge already encoded in a WorldSpec.

Only evidence quotes are source facts. Concepts, rules and actions are authored
design inferences; narrative is kept separately, never promoted to evidence.
This indexes a design, not all knowledge in a document or a learner's mastery.
"""

from copy import deepcopy
import hashlib
import json
import re
from typing import Annotated, Literal

from pydantic import Field

from .world import schema_check, unique, validate_mechanics, world_hash
from .world_schema import Data, Id, Text, WORLD_SCHEMA

MAX_SOURCE_CHARS = 60000
MAX_CONTEXT_WORLDS = 8
MAX_CONTEXT_ITEMS = 12
MAX_CONTEXT_EVIDENCE_CHARS = 6000
MAX_CONTEXT_CHARS = 12000
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
References = Annotated[list[Id], Field(min_length=1, max_length=288)]


class Source(Data):
    id: Id
    sha256: Digest
    length: Annotated[int, Field(ge=1, le=MAX_SOURCE_CHARS)]


class Evidence(Data):
    id: Id
    provenance: Literal["source_fact"]
    sourceId: Id
    quote: Annotated[str, Field(min_length=1, max_length=MAX_SOURCE_CHARS)]
    start: Annotated[int, Field(ge=0, le=MAX_SOURCE_CHARS)]
    end: Annotated[int, Field(ge=1, le=MAX_SOURCE_CHARS)]


class Concept(Data):
    id: Id
    provenance: Literal["design_inference"]
    label: Text


class Skill(Data):
    id: Id
    provenance: Literal["design_inference"]
    name: Text  # Preserve the exact BKT key, including case and dots.


class Binding(Data):
    puzzleId: Id
    ruleId: Id
    mechanicPaths: Annotated[list[Text], Field(min_length=1, max_length=32)]


class KnowledgeRule(Data):
    id: Id
    provenance: Literal["design_inference"]
    description: Text
    skillId: Id
    evidenceIds: References
    bindings: Annotated[list[Binding], Field(min_length=1, max_length=288)]


class Action(Data):
    id: Id
    provenance: Literal["design_inference"]
    text: Text
    conceptId: Id
    ruleIds: References
    puzzleIds: References


class Narrative(Data):
    id: Id
    provenance: Literal["narrative_fiction"]
    text: Text
    worldPaths: Annotated[list[Text], Field(min_length=1, max_length=700)]


class Edge(Data):
    id: Id
    origin: Id
    target: Id
    relation: Literal["applies_concept", "uses_rule", "trains_skill", "grounded_in"]


class KnowledgeGraph(Data):
    format: Literal["mindcrafted-knowledge-graph"]
    version: Literal[1]
    worldId: Id
    worldHash: Digest
    source: Source
    puzzleIds: Annotated[list[Id], Field(min_length=1, max_length=24)]
    concepts: Annotated[list[Concept], Field(min_length=1, max_length=24)]
    skills: Annotated[list[Skill], Field(min_length=1, max_length=288)]
    rules: Annotated[list[KnowledgeRule], Field(min_length=1, max_length=288)]
    actions: Annotated[list[Action], Field(min_length=1, max_length=24)]
    evidence: Annotated[list[Evidence], Field(min_length=1, max_length=288)]
    narrative: Annotated[list[Narrative], Field(max_length=700)]
    edges: Annotated[list[Edge], Field(min_length=1, max_length=1200)]


KNOWLEDGE_GRAPH_SCHEMA = KnowledgeGraph.model_json_schema()
_TABLES = ("concepts", "skills", "rules", "actions", "evidence", "narrative", "edges")


def _normalized(text):
    return " ".join(text.split()).casefold()


def _id(kind, *values):
    value = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return kind + "_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def _source_metadata(source):
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_SOURCE_CHARS:
        raise ValueError("KnowledgeGraph necesita material de 1 a 60000 caracteres")
    digest = hashlib.sha256(source.encode()).hexdigest()
    return {"id": _id("source", digest), "sha256": digest, "length": len(source)}


def _source_index(source):
    """Map case-folded characters back to Python Unicode character offsets."""
    chars, spans = [], []
    previous_end = 0
    for token in re.finditer(r"\S+", source):
        if chars:
            chars.append(" ")
            spans.append((previous_end, token.start()))
        for offset, char in enumerate(token.group(), token.start()):
            folded = char.casefold()
            chars.extend(folded)
            spans.extend([(offset, offset + 1)] * len(folded))
        previous_end = token.end()
    return "".join(chars), spans


def _evidence(source, index, metadata, text):
    normalized, spans = index
    needle = _normalized(text)
    position = normalized.find(needle) if needle else -1
    while position >= 0:
        start, end = spans[position][0], spans[position + len(needle) - 1][1]
        quote = source[start:end]
        # A match must not consume only half of a Unicode case-fold expansion.
        if _normalized(quote) == needle:
            return {"id": _id("evidence", metadata["sha256"], start, end),
                    "provenance": "source_fact", "sourceId": metadata["id"],
                    "quote": quote, "start": start, "end": end}
        position = normalized.find(needle, position + 1)
    raise ValueError("La evidencia no tiene un span literal en el material")


def _mechanic_paths(puzzle, rule_id):
    mechanics = puzzle["mechanics"]
    groups = {"switch_sequence": ("constraints",), "route_network": ("nodes", "packets"),
              "push_blocks": ("blocks", "goals"), "node_connect": ("connectionRules", "goals"), "resource_balance": ("allocationRules", "goals"),
              "machine_configuration": ("configurationRules", "goals")}[mechanics["archetype"]]
    return [f"/mechanics/{group}/{i}" for group in groups for i, item in enumerate(mechanics[group])
            if item["ruleId"] == rule_id]


def _expected_edges(graph):
    edges = set()
    for action in graph["actions"]:
        edges.add((action["id"], action["conceptId"], "applies_concept"))
        edges.update((action["id"], rid, "uses_rule") for rid in action["ruleIds"])
    for rule in graph["rules"]:
        edges.add((rule["id"], rule["skillId"], "trains_skill"))
        edges.update((rule["id"], eid, "grounded_in") for eid in rule["evidenceIds"])
    return edges


def build_knowledge_graph(world, source):
    """Index a WorldSpec and literal source; reject invalid knowledge references.

    Does not run solvers, an AI judge, or network calls. World publication still
    requires the existing QualityGate. Evidence offsets use Python characters,
    with an exclusive end, rather than UTF-8 bytes or JavaScript UTF-16 units.
    """
    metadata = _source_metadata(source)
    schema_check(world, WORLD_SCHEMA)
    unique(world["puzzles"], "puzzles")
    tables = {name: {} for name in _TABLES}
    index = _source_index(source)

    def add(table, item):
        return tables[table].setdefault(item["id"], item)

    def narrative(text, path):
        item = add("narrative", {"id": _id("narrative", text), "provenance": "narrative_fiction",
                                 "text": text, "worldPaths": []})
        item["worldPaths"].append(path)

    for key in ("title", "introduction"):
        narrative(world[key], "/" + key)
    for i, puzzle in enumerate(world["puzzles"]):
        validate_mechanics(puzzle, source)
        knowledge = puzzle["knowledge"]
        cid = _id("concept", _normalized(knowledge["concept"]))
        add("concepts", {"id": cid, "label": knowledge["concept"], "provenance": "design_inference"})
        rule_ids = []
        for rule in knowledge["requiredRules"]:
            evidence = add("evidence", _evidence(source, index, metadata, rule["evidence"]))
            sid = _id("skill", rule["skill"])
            add("skills", {"id": sid, "name": rule["skill"], "provenance": "design_inference"})
            rid = _id("rule", _normalized(rule["description"]), sid, [evidence["id"]])
            entry = add("rules", {"id": rid, "description": rule["description"], "skillId": sid,
                                  "provenance": "design_inference", "evidenceIds": [evidence["id"]], "bindings": []})
            entry["bindings"].append({"puzzleId": puzzle["id"], "ruleId": rule["id"],
                                      "mechanicPaths": _mechanic_paths(puzzle, rule["id"])})
            if rid not in rule_ids:
                rule_ids.append(rid)
        aid = _id("action", cid, _normalized(knowledge["learning_action"]), sorted(rule_ids))
        action = add("actions", {"id": aid, "text": knowledge["learning_action"], "conceptId": cid,
                                 "provenance": "design_inference", "ruleIds": rule_ids, "puzzleIds": []})
        action["puzzleIds"].append(puzzle["id"])
        for key in ("title", "introduction", "reflection"):
            narrative(puzzle[key], f"/puzzles/{i}/{key}")
    for i, dialogue in enumerate(world["dialogues"]):
        for j, line in enumerate(dialogue["lines"]):
            narrative(line["text"], f"/dialogues/{i}/lines/{j}/text")
    graph = {"format": "mindcrafted-knowledge-graph", "version": 1, "worldId": world["id"],
             "worldHash": world_hash(world), "source": metadata, "puzzleIds": [p["id"] for p in world["puzzles"]],
             **{name: list(items.values()) for name, items in tables.items()}}
    graph["edges"] = [{"id": _id("edge", *edge), "origin": edge[0], "target": edge[1], "relation": edge[2]}
                      for edge in sorted(_expected_edges(graph))]
    validate_knowledge_graph(graph, source)
    return graph


def _distinct(values, label):
    if len(set(values)) != len(values):
        raise ValueError(f"Valores duplicados en {label}")


def validate_knowledge_graph(graph, source=None):
    """Raise ValueError for malformed graphs; source additionally verifies quotes.

    Without the original source this checks structure and offsets only, not the
    authenticity of a quoted fact. It is not a semantic educational validator.
    """
    schema_check(graph, KNOWLEDGE_GRAPH_SCHEMA)
    tables = {name: unique(graph[name], name) for name in _TABLES}
    unique([item for name in _TABLES for item in graph[name]], "KnowledgeGraph")
    unique([{"id": pid} for pid in graph["puzzleIds"]], "puzzleIds")
    unique([{"id": graph["worldId"]}], "worldId")
    puzzles = set(graph["puzzleIds"])
    canonical = [(graph["source"], _id("source", graph["source"]["sha256"]))]
    canonical += [(c, _id("concept", _normalized(c["label"]))) for c in graph["concepts"]]
    canonical += [(s, _id("skill", s["name"])) for s in graph["skills"]]
    canonical += [(r, _id("rule", _normalized(r["description"]), r["skillId"], r["evidenceIds"])) for r in graph["rules"]]
    canonical += [(a, _id("action", a["conceptId"], _normalized(a["text"]), sorted(a["ruleIds"]))) for a in graph["actions"]]
    canonical += [(e, _id("evidence", graph["source"]["sha256"], e["start"], e["end"])) for e in graph["evidence"]]
    canonical += [(n, _id("narrative", n["text"])) for n in graph["narrative"]]
    canonical += [(e, _id("edge", e["origin"], e["target"], e["relation"])) for e in graph["edges"]]
    if any(item["id"] != expected for item, expected in canonical):
        raise ValueError("ID no canónico en KnowledgeGraph")
    for name, field in (("concepts", "label"), ("skills", "name"), ("rules", "description"),
                        ("actions", "text"), ("evidence", "quote"), ("narrative", "text")):
        if any(not _normalized(item[field]) for item in graph[name]):
            raise ValueError(f"Texto vacío en {name}")
    if source is not None and graph["source"] != _source_metadata(source):
        raise ValueError("La fuente no coincide con el hash del KnowledgeGraph")
    for evidence in graph["evidence"]:
        if (evidence["sourceId"] != graph["source"]["id"]
                or not 0 <= evidence["start"] < evidence["end"] <= graph["source"]["length"]
                or evidence["end"] - evidence["start"] != len(evidence["quote"])):
            raise ValueError("Referencia o span de evidencia inválido")
        if source is not None and source[evidence["start"]:evidence["end"]] != evidence["quote"]:
            raise ValueError("La cita no coincide literalmente con el material")
    seen_bindings = set()
    for rule in graph["rules"]:
        _distinct(rule["evidenceIds"], "evidenceIds")
        if rule["skillId"] not in tables["skills"] or not set(rule["evidenceIds"]) <= tables["evidence"].keys():
            raise ValueError("Regla con habilidad o evidencia inexistente")
        for binding in rule["bindings"]:
            unique([{"id": binding["ruleId"]}], "binding.ruleId")
            key = binding["puzzleId"], binding["ruleId"]
            if binding["puzzleId"] not in puzzles or key in seen_bindings:
                raise ValueError("Binding duplicado o puzzle inexistente")
            seen_bindings.add(key)
            _distinct(binding["mechanicPaths"], "mechanicPaths")
            if any(not re.fullmatch(r"/mechanics/(constraints|nodes|packets|blocks|goals|connectionRules|allocationRules|configurationRules)/\d+", path)
                   for path in binding["mechanicPaths"]):
                raise ValueError("Ruta de mecánica inválida")
    covered_puzzles = set()
    for action in graph["actions"]:
        _distinct(action["ruleIds"], "ruleIds")
        _distinct(action["puzzleIds"], "puzzleIds")
        if (action["conceptId"] not in tables["concepts"] or not set(action["ruleIds"]) <= tables["rules"].keys()
                or not set(action["puzzleIds"]) <= puzzles):
            raise ValueError("Acción con referencia inexistente")
        if covered_puzzles.intersection(action["puzzleIds"]):
            raise ValueError("Puzzle con acciones duplicadas")
        covered_puzzles.update(action["puzzleIds"])
        for pid in action["puzzleIds"]:
            expected = {rule["id"] for rule in graph["rules"] if any(b["puzzleId"] == pid for b in rule["bindings"])}
            if set(action["ruleIds"]) != expected:
                raise ValueError("Acción con reglas ajenas o incompletas")
    _distinct([path for item in graph["narrative"] for path in item["worldPaths"]], "worldPaths")
    for item in graph["narrative"]:
        if any(not re.fullmatch(r"/(title|introduction|puzzles/\d+/(title|introduction|reflection)|dialogues/\d+/lines/\d+/text)", path)
               for path in item["worldPaths"]):
            raise ValueError("Ruta narrativa inválida")
    actual = [(edge["origin"], edge["target"], edge["relation"]) for edge in graph["edges"]]
    _distinct(actual, "edges")
    if set(actual) != _expected_edges(graph) or covered_puzzles != puzzles:
        raise ValueError("Grafo con enlaces inexistentes o incompletos")
    for name, used in (("concepts", {a["conceptId"] for a in graph["actions"]}),
                       ("skills", {r["skillId"] for r in graph["rules"]}),
                       ("evidence", {e for r in graph["rules"] for e in r["evidenceIds"]})):
        if set(tables[name]) != used:
            raise ValueError(f"Nodos huérfanos en {name}")


def _previous_graph(previous):
    if not isinstance(previous, dict):
        raise ValueError("Se esperaba un grafo, paquete o {world, source}")
    if "source" in previous and "world" in previous:
        return build_knowledge_graph(previous["world"], previous["source"])
    graph = previous.get("knowledgeGraph", previous)
    validate_knowledge_graph(graph)
    if "world" in previous and (graph["worldHash"] != world_hash(previous["world"])
                                or graph["worldId"] != previous["world"].get("id")):
        raise ValueError("El grafo no corresponde al mundo del paquete")
    source_hash = previous.get("config", {}).get("sourceHash")
    if source_hash is not None and source_hash != graph["source"]["sha256"]:
        raise ValueError("El grafo no corresponde a la fuente del paquete")
    return graph


def learning_context(previous_worlds):
    """Compact prior design knowledge, most recent lessons first (not BKT mastery).

    Accepts a chronological list/tuple of graphs, packages with knowledgeGraph,
    or {world, source} pairs. Original sources are rechecked when supplied.
    Caps: eight lessons, twelve rules/concepts/skills, 6000 quote characters and
    12000 JSON characters. Whole evidence spans are retained or omitted.
    """
    if not isinstance(previous_worlds, (list, tuple)):
        raise ValueError("previous_worlds debe ser una lista cronológica")
    context = {"format": "mindcrafted-learning-context", "version": 1, "mastery": "not_assessed",
               "concepts": [], "skills": [], "rules": [], "truncated": len(previous_worlds) > MAX_CONTEXT_WORLDS}
    evidence_chars, seen = 0, set()
    for previous in reversed(previous_worlds[-MAX_CONTEXT_WORLDS:]):
        graph = _previous_graph(previous)
        concepts = {c["id"]: c["label"] for c in graph["concepts"]}
        skills = {s["id"]: s["name"] for s in graph["skills"]}
        rules = {r["id"]: r for r in graph["rules"]}
        evidence = {e["id"]: e for e in graph["evidence"]}
        for action in graph["actions"]:
            for rid in action["ruleIds"]:
                rule = rules[rid]
                quotes = [{"sourceHash": graph["source"]["sha256"], "provenance": "source_fact",
                           **{key: evidence[eid][key] for key in ("quote", "start", "end")}}
                          for eid in rule["evidenceIds"]]
                concept, skill = concepts[action["conceptId"]], skills[rule["skillId"]]
                key = (_normalized(concept), skill, _normalized(rule["description"]),
                       _normalized(action["text"]), tuple(_normalized(e["quote"]) for e in quotes))
                if key in seen:
                    continue
                seen.add(key)
                count = sum(len(e["quote"]) for e in quotes)
                if len(context["rules"]) >= MAX_CONTEXT_ITEMS or evidence_chars + count > MAX_CONTEXT_EVIDENCE_CHARS:
                    context["truncated"] = True
                    continue
                candidate = deepcopy(context)
                if _normalized(concept) not in {_normalized(c) for c in candidate["concepts"]}:
                    candidate["concepts"].append(concept)
                if skill not in candidate["skills"]:
                    candidate["skills"].append(skill)
                candidate["rules"].append({"worldId": graph["worldId"], "worldHash": graph["worldHash"],
                                           "concept": concept, "skill": skill, "description": rule["description"],
                                           "learningAction": action["text"], "provenance": "design_inference",
                                           "evidence": quotes})
                if len(json.dumps(candidate, ensure_ascii=False)) > MAX_CONTEXT_CHARS:
                    context["truncated"] = True
                    continue
                context = candidate
                evidence_chars += count
    return context
