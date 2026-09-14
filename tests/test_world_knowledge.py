from copy import deepcopy
import hashlib
import json

import pytest

from mindcrafted.generator.world import compile_world, world_hash
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint
from mindcrafted.generator.world_knowledge import (
    MAX_CONTEXT_CHARS,
    MAX_CONTEXT_EVIDENCE_CHARS,
    MAX_CONTEXT_ITEMS,
    MAX_CONTEXT_WORLDS,
    build_knowledge_graph,
    learning_context,
    validate_knowledge_graph,
)


@pytest.fixture
def graph(world_spec):
    return build_knowledge_graph(world_spec, SOURCE)


def test_graph_traces_all_archetypes_to_exact_source_and_mechanics(world_spec, graph):
    assert len(graph["concepts"]) == len(graph["actions"]) == 3
    assert len(graph["rules"]) == 8
    assert len(graph["skills"]) == 7  # network.routing is shared across archetypes.
    assert graph["source"]["sha256"] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert graph["worldHash"] == world_hash(world_spec)
    puzzles = {p["id"]: p for p in world_spec["puzzles"]}
    evidence = {e["id"]: e for e in graph["evidence"]}
    for rule in graph["rules"]:
        assert rule["provenance"] == "design_inference"
        for eid in rule["evidenceIds"]:
            span = evidence[eid]
            assert span["quote"] == SOURCE[span["start"]:span["end"]]
            assert span["provenance"] == "source_fact"
        for binding in rule["bindings"]:
            for path in binding["mechanicPaths"]:
                _, mechanics, group, index = path.split("/")
                assert puzzles[binding["puzzleId"]][mechanics][group][int(index)]["ruleId"] == binding["ruleId"]
    validate_knowledge_graph(json.loads(json.dumps(graph)), SOURCE)


def test_extraction_is_deterministic_and_does_not_mutate_or_run_solvers(world_spec, monkeypatch):
    import mindcrafted.generator.world as world_module

    def forbidden_solver(*args, **kwargs):
        pytest.fail("Knowledge extraction must not rerun combinatorial solvers")

    monkeypatch.setattr(world_module, "solve_puzzle", forbidden_solver)
    original = deepcopy(world_spec)
    first = build_knowledge_graph(world_spec, SOURCE)
    assert first == build_knowledge_graph(world_spec, SOURCE)
    first["actions"][0]["text"] = "changed"
    assert world_spec == original


def test_unicode_whitespace_and_case_matching_preserves_original_offsets(world_spec):
    quote = "Straße\t— LOS ROUTERS\r\n   procesan paquetes."
    source = "🛰️ Introducción.\n" + quote + "\n" + SOURCE + quote
    world_spec["puzzles"][0]["knowledge"]["requiredRules"][0]["evidence"] = "STRASSE — los routers procesan paquetes."
    graph = build_knowledge_graph(world_spec, source)
    evidence = next(e for e in graph["evidence"] if e["quote"] == quote)
    assert evidence["start"] == source.index(quote)
    assert evidence["end"] == source.index(quote) + len(quote)
    validate_knowledge_graph(graph, source)


def test_rule_ids_are_scoped_by_puzzle_not_silently_overwritten(world_spec):
    sequence = world_spec["puzzles"][1]
    sequence["knowledge"]["requiredRules"][0]["id"] = "capacity"
    sequence["mechanics"]["constraints"][0]["ruleId"] = "capacity"
    graph = build_knowledge_graph(world_spec, SOURCE)
    rules = [r for r in graph["rules"] if any(b["ruleId"] == "capacity" for b in r["bindings"])]
    assert len(rules) == 2
    assert rules[0]["id"] != rules[1]["id"]
    assert rules[0]["evidenceIds"] != rules[1]["evidenceIds"]


def test_semantic_duplicates_merge_without_losing_local_bindings():
    blueprint = demo_blueprint()
    duplicate = deepcopy(blueprint["puzzles"][0])
    duplicate["id"] = "routing_again"
    duplicate["knowledge"]["concept"] = "ROUTING  Y CONGESTIÓN"
    duplicate["knowledge"]["requiredRules"][0]["id"] = "second_capacity"
    for node in duplicate["mechanics"]["nodes"]:
        node["ruleId"] = "second_capacity"
    blueprint["puzzles"].append(duplicate)
    graph = build_knowledge_graph(compile_world(blueprint, SOURCE), SOURCE)
    assert len(graph["concepts"]) == len(graph["actions"]) == 1
    assert len(graph["rules"]) == len(graph["evidence"]) == len(graph["skills"]) == 2
    assert graph["actions"][0]["puzzleIds"] == ["routing", "routing_again"]
    capacity = next(r for r in graph["rules"] if "capacidad" in r["description"])
    assert {b["ruleId"] for b in capacity["bindings"]} == {"capacity", "second_capacity"}
    assert len(graph["edges"]) == len({(e["origin"], e["target"], e["relation"]) for e in graph["edges"]})


def test_fiction_and_authored_interpretation_never_become_source_facts(world_spec):
    fiction = "La compuerta funciona gracias a dragones de cristal."
    world_spec["puzzles"][0]["reflection"] = fiction
    graph = build_knowledge_graph(world_spec, SOURCE)
    assert next(n for n in graph["narrative"] if n["text"] == fiction)["provenance"] == "narrative_fiction"
    assert all(e["quote"] in SOURCE for e in graph["evidence"])
    assert fiction not in json.dumps(learning_context([graph]), ensure_ascii=False)
    # Matching a quote is not a semantic endorsement of an authored description.
    world_spec["puzzles"][0]["knowledge"]["requiredRules"][0]["description"] = fiction
    graph = build_knowledge_graph(world_spec, SOURCE)
    assert next(r for r in graph["rules"] if r["description"] == fiction)["provenance"] == "design_inference"


@pytest.mark.parametrize("mutate", [
    lambda w: w["puzzles"][0]["knowledge"]["requiredRules"][0].update(evidence="No consta esta afirmación en ningún material."),
    lambda w: w["puzzles"][0]["knowledge"]["requiredRules"][0].update(evidence=" " * 20),
    lambda w: w["puzzles"][0]["knowledge"]["requiredRules"].append(deepcopy(w["puzzles"][0]["knowledge"]["requiredRules"][0])),
    lambda w: w["puzzles"][0]["mechanics"]["nodes"][0].update(ruleId="missing"),
    lambda w: w["puzzles"][0].update(id="../escape"),
    lambda w: w["puzzles"].append(deepcopy(w["puzzles"][0])),
])
def test_extractor_rejects_untraceable_evidence_and_invalid_knowledge(world_spec, mutate):
    mutate(world_spec)
    with pytest.raises(ValueError):
        build_knowledge_graph(world_spec, SOURCE)


@pytest.mark.parametrize("mutate", [
    lambda g: g["rules"].append(deepcopy(g["rules"][0])),
    lambda g: g["concepts"].append(dict(g["concepts"][0], id="same_concept_other_id")),
    lambda g: g["rules"][0].update(id="constructor"),
    lambda g: g["rules"][0].update(skillId="missing"),
    lambda g: g["rules"][0]["evidenceIds"].append("missing"),
    lambda g: g["rules"][0]["bindings"][0].update(puzzleId="missing"),
    lambda g: g["rules"][0]["bindings"].append(deepcopy(g["rules"][0]["bindings"][0])),
    lambda g: g["rules"][0]["bindings"][0].update(mechanicPaths=["/../../private"]),
    lambda g: g["actions"][0].update(conceptId="missing"),
    lambda g: g["actions"][0]["puzzleIds"].append("missing"),
    lambda g: g["evidence"][0].update(provenance="design_inference"),
    lambda g: g["evidence"][0].update(quote=g["evidence"][0]["quote"].swapcase()),
    lambda g: g["evidence"][0].update(end=g["source"]["length"] + 1),
    lambda g: g["source"].update(id="missing"),
    lambda g: g["edges"].pop(),
    lambda g: g["edges"].append(deepcopy(g["edges"][0])),
    lambda g: g["edges"][0].update(target="missing"),
    lambda g: g["narrative"][0]["worldPaths"].append(g["narrative"][0]["worldPaths"][0]),
    lambda g: g.update(javascript="alert(1)"),
])
def test_graph_validation_rejects_corruption(graph, mutate):
    mutate(graph)
    with pytest.raises(ValueError):
        validate_knowledge_graph(graph, SOURCE)


def test_changed_source_cannot_reuse_graph(graph):
    with pytest.raises(ValueError, match="fuente"):
        validate_knowledge_graph(graph, SOURCE + "Otra frase.")


def test_learning_context_accepts_packages_and_source_pairs_without_mastery_claim(world_spec, graph):
    package = {"world": world_spec, "knowledgeGraph": graph,
               "config": {"sourceHash": graph["source"]["sha256"]}}
    original = deepcopy(package)
    context = learning_context([package, {"world": world_spec, "source": SOURCE}, graph])
    assert context == learning_context([graph])
    assert set(context["skills"]) == {s["name"] for s in graph["skills"]}
    assert context["mastery"] == "not_assessed"
    assert context["truncated"] is False
    for rule in context["rules"]:
        for evidence in rule["evidence"]:
            assert evidence["quote"] == SOURCE[evidence["start"]:evidence["end"]]
            assert evidence["sourceHash"] == graph["source"]["sha256"]
    assert package == original
    context["rules"][0]["description"] = "changed"
    assert package == original


def test_learning_context_rejects_stale_package_and_rechecks_supplied_source(world_spec, graph):
    world_spec["title"] = "Nuevo mundo"
    with pytest.raises(ValueError, match="mundo"):
        learning_context([{"world": world_spec, "knowledgeGraph": graph}])
    with pytest.raises(ValueError, match="fuente"):
        learning_context([{"knowledgeGraph": graph, "config": {"sourceHash": "0" * 64}}])
    with pytest.raises(ValueError, match="evidencia"):
        learning_context([{"world": world_spec, "source": "Contenido sin ninguna de las reglas anteriores."}])


def test_context_limits_choose_recent_lessons_and_keep_complete_evidence(world_spec):
    previous = []
    for i in range(MAX_CONTEXT_WORLDS + 2):
        world = deepcopy(world_spec)
        world["id"] = f"lesson_{i}"
        for puzzle in world["puzzles"]:
            puzzle["knowledge"]["concept"] += f" / lesson {i}"
        previous.append(build_knowledge_graph(world, SOURCE))
    context = learning_context(previous)
    assert context["truncated"] is True
    assert context["rules"][0]["worldId"] == f"lesson_{len(previous) - 1}"
    assert len(context["rules"]) <= MAX_CONTEXT_ITEMS
    assert len(context["concepts"]) <= MAX_CONTEXT_ITEMS
    assert len(context["skills"]) <= MAX_CONTEXT_ITEMS
    assert len(json.dumps(context, ensure_ascii=False)) <= MAX_CONTEXT_CHARS
    assert sum(len(e["quote"]) for r in context["rules"] for e in r["evidence"]) <= MAX_CONTEXT_EVIDENCE_CHARS
    for rule in context["rules"]:
        for evidence in rule["evidence"]:
            assert evidence["quote"] == SOURCE[evidence["start"]:evidence["end"]]


def test_large_literal_span_is_omitted_without_truncating_quote(world_spec):
    phrase = "Cada router puede procesar dos paquetes a la vez."
    expanded = phrase.replace(" ", " " * 1000)
    source = SOURCE.replace(phrase, expanded)
    context = learning_context([{"world": world_spec, "source": source}])
    assert context["truncated"] is True
    assert context["rules"]  # Smaller grounded facts still fit the context.
    assert "network.load_balance" not in context["skills"]
    for rule in context["rules"]:
        for evidence in rule["evidence"]:
            assert evidence["quote"] == source[evidence["start"]:evidence["end"]]


def test_empty_history_is_valid_and_unsupported_unverified_inputs_are_rejected(world_spec):
    assert learning_context([])["rules"] == []
    for value in (None, SOURCE, "x" * 60001):
        with pytest.raises(ValueError):
            build_knowledge_graph(world_spec, value if value != SOURCE else "")
    for value in (None, {}, [world_spec], [None]):
        with pytest.raises(ValueError):
            learning_context(value)
