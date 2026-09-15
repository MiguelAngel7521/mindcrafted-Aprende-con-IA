"""Bake-off fairness and selection, without any live provider calls."""
import asyncio
from copy import deepcopy
import json

import pytest

from mindcrafted.generator import api
from mindcrafted.generator.model_bakeoff import (Bakeoff, REQUIRED_PARAMETERS, SETTINGS, THRESHOLDS,
    assert_resume_contract, evaluate_candidate, model_profile, select_finalists, summarize)
from mindcrafted.generator.node_connect_demo import SOURCE, blueprint
from mindcrafted.generator.provider_response import GenerationError
from mindcrafted.generator.structured_schema import blueprint_response_schema, strict_response_schema
from test_ai_provider_contract import provider_script, completion


def candidate():
    design = blueprint()
    design["puzzles"][0]["role"] = "challenge"
    return design


def evaluate(design):
    canonical = blueprint_response_schema("node_connect")
    return evaluate_candidate(json.dumps(design), SOURCE, canonical, strict_response_schema(canonical))


def row(**changes):
    return {"providerResponse": True, "jsonParse": True, "schemaValid": True,
            "semanticValid": True, "groundingValid": True, "failures": [],
            "providerRetries": 0, "providerErrors": [], "events": [], **changes}


def test_sampling_parameters_are_sent_to_the_provider(provider_script):
    script, requests, events, _ = provider_script
    script.append(completion("valid"))
    asyncio.run(api.generate("prompt", "system", model="fixed-model", temperature=.2, top_p=1.))
    assert requests[0]["temperature"] == .2 and requests[0]["top_p"] == 1.
    assert events[0]["temperature"] == .2 and events[0]["top_p"] == 1.


def test_probe_reports_literal_spans_without_compiling():
    result = evaluate(candidate())
    assert all(result[key] for key in ("jsonParse", "schemaValid", "semanticValid", "groundingValid"))
    assert result["evidence"]
    for span in result["evidence"]:
        assert SOURCE[span["start"]:span["end"]] == span["quote"]


@pytest.mark.parametrize("fault,category", [("envelope", "LLM_INVALID_ENVELOPE"),
    ("schema", "LLM_SCHEMA_ERROR"), ("reference", "INCONSISTENT_GOAL"), ("grounding", "GROUNDING_ERROR")])
def test_probe_distinguishes_structure_semantics_and_grounding(fault, category):
    design = candidate()
    if fault == "envelope":
        design = design["puzzles"][0]
    elif fault == "schema":
        design["unknown"] = True
    elif fault == "reference":
        design["puzzles"][0]["mechanics"]["goals"][0]["target"] = "missing"
    else:
        design["puzzles"][0]["knowledge"]["requiredRules"][0]["evidence"] = "A fabricated fact absent from this educational source."
    result = evaluate(design)
    assert result["jsonParse"] and not result["semanticValid"]
    assert result["failures"][0]["category"] == category
    assert result["schemaValid"] == (fault in ("reference", "grounding"))
    if fault == "reference":
        assert result["groundingValid"]  # Literal grounding does not repair a bad reference.


def test_json_parse_failure_does_not_count_as_json_success():
    canonical = blueprint_response_schema("node_connect")
    result = evaluate_candidate('{"title":', SOURCE, canonical, strict_response_schema(canonical))
    assert not result["jsonParse"] and result["failures"][0]["category"] == "LLM_JSON_PARSE_ERROR"


def test_thresholds_are_fixed_and_a_good_score_cannot_override_them():
    assert THRESHOLDS == {"providerResponseRate": .90, "schemaSuccessRate": .90, "semanticSuccessRate": .80}
    weak = summarize([row() for _ in range(3)] + [row(semanticValid=False) for _ in range(2)], 5)
    assert weak["reliabilityScore"] > 60 and not weak["eligible"]
    assert select_finalists({"weak": {"metrics": weak}}) == []
    borderline = summarize([row() for _ in range(4)] + [row(semanticValid=False)], 5)
    assert borderline["eligible"] and borderline["semanticRepairNeeded"] == 1
    schema_failure = summarize([row() for _ in range(4)] + [row(schemaValid=False, semanticValid=False)], 5)
    assert not schema_failure["eligible"]


def test_incomplete_and_rounded_results_cannot_win():
    incomplete = summarize([row() for _ in range(4)], 5)
    assert incomplete["providerResponseRate"] == .8 and not incomplete["eligible"]
    below = summarize([row() for _ in range(89)] + [row(schemaValid=False) for _ in range(11)], 100)
    assert not below["eligible"]


def test_finalist_ranking_prioritizes_semantics_over_latency():
    weaker = summarize([row() for _ in range(4)] + [row(semanticValid=False)], 5)
    stronger = summarize([row(providerRetries=1) for _ in range(5)], 5)
    assert select_finalists({"fast": {"metrics": weaker}, "accurate": {"metrics": stronger}}, 1) == ["accurate"]


def test_profiles_require_live_available_capabilities_without_claiming_strict_guarantees():
    catalog = {"data": [{"id": "fixed/model", "supported_parameters": list(REQUIRED_PARAMETERS)}]}
    endpoint = {"status": 0, "supported_parameters": list(REQUIRED_PARAMETERS), "max_completion_tokens": 20000}
    profile = model_profile("fixed/model", catalog, {"data": {"endpoints": [endpoint]}})
    assert profile["eligibleEndpoint"] and profile["supportsStructuredOutput"]
    assert profile["supportsStrictSchema"] is None
    for changed in ({**endpoint, "status": -5}, {**endpoint, "supported_parameters": ["response_format"]}):
        assert not model_profile("fixed/model", catalog, {"data": {"endpoints": [changed]}})["eligibleEndpoint"]
    with pytest.raises(ValueError, match="fixed ID"):
        model_profile("invented/model", catalog, {"data": {"endpoints": []}})


def test_first_round_uses_identical_contract_and_never_repairs(tmp_path):
    calls = []
    invalid = candidate()
    invalid["puzzles"][0]["mechanics"]["goals"][0]["target"] = "missing"

    async def generate(prompt, system, **kwargs):
        calls.append((prompt, system, deepcopy(kwargs)))
        api._provider_events_ctx.get().append({"http_status": 200, "attempt": 1, "latency_ms": 1, "error_category": None})
        return json.dumps(invalid)

    runner = Bakeoff(SOURCE, tmp_path, generate=generate)
    result = asyncio.run(runner.round(["model/a", "model/b", "model/c"], 1, 5))
    assert len(calls) == 15 and len({(prompt, system) for prompt, system, _ in calls}) == 1
    for prompt, _, settings in calls:
        assert "repair" not in json.loads(prompt) and settings["repair_count"] == 0
        assert all(settings[key] == value for key, value in SETTINGS.items())
    assert select_finalists(result) == [] and not (tmp_path / "campaign").exists()


def test_balanced_but_truncated_response_never_becomes_semantic_success(tmp_path):
    async def generate(*args, **kwargs):
        raise GenerationError("LLM_TRUNCATED_RESPONSE", "limit", candidate=json.dumps(candidate()))
    runner = Bakeoff(SOURCE, tmp_path, generate=generate)
    result = asyncio.run(runner.probe("model/a", tmp_path / "probe", "probe-1"))
    assert result["schemaValid"] and not result["semanticValid"]


def test_repairability_uses_only_real_saved_invalid_candidates(tmp_path):
    original = candidate()
    original["puzzles"][0]["mechanics"]["goals"][0]["target"] = "missing"
    saved = tmp_path / "original.txt"
    saved.write_text(json.dumps(original))
    calls = []

    async def generate(prompt, system, **kwargs):
        calls.append(json.loads(prompt)["repair"])
        assert kwargs["repair_count"] == 1
        return json.dumps(candidate())

    runner = Bakeoff(SOURCE, tmp_path, generate=generate)
    result = asyncio.run(runner.repairability("model/a", [{"model/a": {"results": [row(semanticValid=False,
        responsePath=str(saved), generationId="original-real-id", failures=[{"category": "INCONSISTENT_GOAL", "diagnostic": "missing"}])]}}]))
    assert result["repairSuccessRate"] == 1. and result["cases"] == 1
    assert calls[0]["candidate"] == saved.read_text()
    assert calls[0]["originalGenerationId"] == "original-real-id"


@pytest.mark.parametrize("key", ["sourceHash", "promptHash", "wireSchemaHash", "settings", "thresholds"])
def test_resume_rejects_any_changed_experiment_contract(key):
    saved = {"sourceHash": "source", "promptHash": "prompt", "wireSchemaHash": "wire",
             "settings": SETTINGS, "thresholds": THRESHOLDS, "createdAt": "yesterday"}
    current = deepcopy(saved)
    current[key] = "changed"
    with pytest.raises(ValueError, match="RESUME_CONTRACT_MISMATCH"):
        assert_resume_contract(saved, current)
    assert_resume_contract(saved, {**saved, "createdAt": "today"})


def test_resume_preserves_completed_samples_and_archives_only_unobserved_requests(tmp_path):
    calls = []

    async def generate(prompt, system, **kwargs):
        calls.append(kwargs["model"])
        return json.dumps(candidate())

    runner = Bakeoff(SOURCE, tmp_path, generate=generate)
    for model in ("model/a", "model/b"):
        directory = tmp_path / "round-1" / model.replace("/", "__") / "probe-01"
        asyncio.run(runner.probe(model, directory, model))
    completed = {path: path.read_bytes() for path in tmp_path.glob("round-1/**/result.json")}
    orphan = tmp_path / "round-1/model__c/probe-01/request.json"
    orphan.parent.mkdir(parents=True)
    orphan.write_text('{"previousRequest":"without observed outcome"}')
    original = orphan.read_bytes()
    calls.clear()
    runner.resume = True
    result = asyncio.run(runner.round(["model/a", "model/b", "model/c"], 1, 1))
    assert calls == ["model/c"]
    assert all(path.read_bytes() == data for path, data in completed.items())
    archived = list(orphan.parent.glob("interruptions/*/request.json"))
    assert len(archived) == 1 and archived[0].read_bytes() == original
    assert result["model/c"]["results"][0]["unobservedRequests"] == 1
    assert all(len(data["results"]) == 1 for data in result.values())
