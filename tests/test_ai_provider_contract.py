"""The real provider boundary, deterministic repair, and fixed-schema requests."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import httpx
from jsonschema import Draft202012Validator
import pytest

from mindcrafted.generator import api
from mindcrafted.generator.node_connect_demo import SOURCE, blueprint
from mindcrafted.generator.provider_response import GenerationError, ProviderError, normalize_response
from mindcrafted.generator.structured_schema import blueprint_response_schema, schema_hash, strict_response_schema
from mindcrafted.generator.world_pipeline import generate_campaign, parse_model_object
from mindcrafted.generator.world_schema import BLUEPRINT_SCHEMA, NodeConnect
from test_api_client_isolation import fake_clients


def completion(content="ok", finish="stop", **extra):
    return {"model": "fixed-model", "choices": [{"message": {"content": content}, "finish_reason": finish}], **extra}


@pytest.fixture
def provider_script(monkeypatch):
    script, requests, events, sleeps = [], [], [], []

    async def create(**kwargs):
        requests.append(deepcopy(kwargs))
        result = script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def sleep(delay):
        sleeps.append(delay)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(api, "_get_client", lambda *args, **kwargs: (client, "test"))
    monkeypatch.setattr(api, "_api_semaphore", None)
    monkeypatch.setattr(api.asyncio, "sleep", sleep)
    token = api._provider_events_ctx.set(events)
    yield script, requests, events, sleeps
    api._provider_events_ctx.reset(token)


@pytest.mark.parametrize("content", ['{"ok":true}', [{"type": "text", "text": '{"ok":'}, {"type": "output_text", "text": 'true}'}]])
def test_provider_normalization_accepts_only_public_content(content):
    raw = completion(content)
    raw["choices"][0]["message"]["reasoning"] = "This is not the answer"
    result = normalize_response(raw, provider="groq", model="fixed-model", fixed_model=True)
    assert result.text == '{"ok":true}' and result.response_model == "fixed-model"


@pytest.mark.parametrize("raw,category", [
    ({"choices": []}, "PROVIDER_EMPTY_RESPONSE"),
    ({}, "PROVIDER_INVALID_RESPONSE"),
    (completion("  "), "PROVIDER_EMPTY_RESPONSE"),
    (completion({}, "stop"), "PROVIDER_INVALID_RESPONSE"),
    ({"error": {"code": 429}}, "PROVIDER_RATE_LIMIT"),
    ({"error": {"code": 408}}, "PROVIDER_TIMEOUT"),
    ({"error": {"code": 401}}, "PROVIDER_HTTP_ERROR"),
    (completion("", "content_filter"), "PROVIDER_REFUSAL"),
    (completion([{"type": "refusal", "refusal": "no"}]), "PROVIDER_REFUSAL"),
    (completion("", "tool_calls"), "PROVIDER_INVALID_RESPONSE"),
    (completion("ok", model="different-model"), "PROVIDER_MODEL_MISMATCH"),
])
def test_provider_failures_have_specific_categories(raw, category):
    with pytest.raises(ProviderError) as caught:
        normalize_response(raw, provider="openrouter", model="fixed-model", fixed_model=True)
    assert caught.value.category == category


def test_truncation_is_a_content_failure_not_an_empty_transport_response(provider_script):
    script, requests, events, sleeps = provider_script
    script.append(completion('{"title":', "length"))
    with pytest.raises(GenerationError, match="LLM_TRUNCATED_RESPONSE"):
        asyncio.run(api.generate("prompt", "system", model="fixed-model", max_retries=3))
    assert len(requests) == 1 and sleeps == [] and events[0]["error_category"] == "LLM_TRUNCATED_RESPONSE"


def test_empty_retries_identical_request_without_consuming_repair(provider_script):
    script, requests, events, sleeps = provider_script
    script.extend([completion(""), completion("valid")])
    assert asyncio.run(api.generate("prompt", "system", model="fixed-model", max_retries=2,
                                   generation_id="generation-a", repair_count=1)) == "valid"
    assert requests[0] == requests[1] and sleeps == [2]
    assert [e["attempt"] for e in events] == [1, 2]
    assert {e["repair_count"] for e in events} == {1}
    assert {e["generation_id"] for e in events} == {"generation-a"}


def test_schema_error_is_recorded_without_retry_or_losing_candidate(provider_script):
    script, requests, events, sleeps = provider_script
    raw = '{"id":"puzzle-instead-of-blueprint"}'
    script.append(completion(raw))
    with pytest.raises(GenerationError, match="LLM_INVALID_ENVELOPE") as caught:
        asyncio.run(api.generate("prompt", "system", model="fixed-model", max_retries=3,
                                 response_schema=blueprint_response_schema("node_connect")))
    assert caught.value.candidate == raw
    assert len(requests) == 1 and sleeps == []
    assert events[0]["error_category"] == "LLM_INVALID_ENVELOPE"
    assert events[0]["http_status"] == 200 and events[0]["response_status"] == "error"


@pytest.mark.parametrize("failure,category,retry", [
    (httpx.ReadTimeout("do-not-log-me"), "PROVIDER_TIMEOUT", True),
    (429, "PROVIDER_RATE_LIMIT", True), (503, "PROVIDER_UPSTREAM_ERROR", True),
    (401, "PROVIDER_HTTP_ERROR", False), (400, "PROVIDER_HTTP_ERROR", False),
])
def test_retry_only_transient_failures_and_never_logs_provider_error_secrets(provider_script, capsys, failure, category, retry):
    script, requests, events, sleeps = provider_script
    if isinstance(failure, int):
        request = httpx.Request("POST", "https://provider.test/v1", headers={"Authorization": "Bearer do-not-log-me"})
        failure = api.APIStatusError("do-not-log-me", response=httpx.Response(failure, request=request), body={"secret": "do-not-log-me"})
    script.extend([failure, completion("valid")])
    if retry:
        assert asyncio.run(api.generate("prompt", "system", model="fixed-model", max_retries=2)) == "valid"
    else:
        with pytest.raises(ProviderError, match=category):
            asyncio.run(api.generate("prompt", "system", model="fixed-model", max_retries=2))
    assert len(requests) == (2 if retry else 1)
    assert events[0]["error_category"] == category
    assert "do-not-log-me" not in capsys.readouterr().err


def test_schema_is_derived_without_relaxing_canonical_constraints():
    original = deepcopy(BLUEPRINT_SCHEMA)
    canonical = blueprint_response_schema("node_connect")
    wire = strict_response_schema(canonical)
    assert BLUEPRINT_SCHEMA == original
    assert canonical["$defs"]["NodeConnect"] == {k: v for k, v in NodeConnect.model_json_schema().items() if k != "$defs"}
    assert wire["$defs"]["NodeConnect"]["properties"]["edges"]["maxItems"] == 12
    assert wire["$defs"]["NodeConnect"]["properties"]["nodes"]["minItems"] == 3
    assert "Network" not in wire["$defs"] and "oneOf" not in json.dumps(wire)
    design = blueprint()
    design["puzzles"][0]["role"] = "challenge"
    Draft202012Validator(wire).validate(design)
    Draft202012Validator(BLUEPRINT_SCHEMA).validate(design)
    design["puzzles"][0]["mechanics"]["javascript"] = "unsafe"
    assert not Draft202012Validator(wire).is_valid(design)
    assert not Draft202012Validator(BLUEPRINT_SCHEMA).is_valid(design)


@pytest.mark.parametrize("provider,mode", [("groq", "strict"), ("openrouter", "strict"), ("openrouter", "best_effort"), ("openai_compatible", "json_mode")])
def test_request_uses_real_response_format_and_pins_model(provider_script, monkeypatch, provider, mode):
    script, requests, events, _ = provider_script
    design = blueprint()
    design["puzzles"][0]["role"] = "challenge"
    script.append(completion(json.dumps(design)))
    monkeypatch.setenv("STUDIO_MODEL_WORLD_BLUEPRINT", "openrouter/free")
    schema = blueprint_response_schema("node_connect")
    asyncio.run(api.generate("prompt", "system", model="fixed-model", fixed_model=True, provider=provider,
                             step="world_blueprint", response_schema=schema, structured_mode=mode,
                             schema_version="world-2/node-1"))
    request = requests[0]
    assert request["model"] == "fixed-model"
    assert request["response_format"]["type"] == ("json_object" if mode == "json_mode" else "json_schema")
    if mode != "json_mode":
        assert request["response_format"]["json_schema"]["strict"] == (mode == "strict")
    if provider == "openrouter":
        assert request["extra_body"]["provider"]["require_parameters"]
        assert request["extra_body"]["reasoning"]["exclude"] is True
    assert events[0]["structured_mode"] == mode and events[0]["schema_version"] == "world-2/node-1"
    assert events[0]["canonical_schema_hash"] == schema_hash(schema)
    expected_wire_hash = schema_hash(strict_response_schema(schema)) if mode == "strict" else schema_hash(schema)
    assert events[0]["wire_schema_hash"] == expected_wire_hash


def test_random_model_router_is_not_a_fixed_model(provider_script):
    with pytest.raises(ProviderError, match="explicit fixed model"):
        asyncio.run(api.generate("prompt", "system", model="openrouter/free", fixed_model=True))
    assert provider_script[1] == []


def test_reasoning_budget_is_explicit_and_separate_from_blueprint_repair(provider_script):
    script, requests, events, _ = provider_script
    script.append(completion("valid"))
    asyncio.run(api.generate("prompt", "system", provider="openrouter", model="fixed-model",
                             fixed_model=True, reasoning_effort="low"))
    assert requests[0]["extra_body"]["reasoning"] == {"exclude": True, "effort": "low"}
    assert events[0]["reasoning_effort"] == "low" and events[0]["repair_count"] == 0


def test_groq_uses_its_own_key_without_borrowing_openrouter_credentials(monkeypatch, fake_clients):
    monkeypatch.setenv("API_KEY", "openrouter-private")
    monkeypatch.setenv("STUDIO_AI_PROVIDER", "openrouter")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No API key"):
        api._get_client(provider="groq")
    assert not fake_clients
    monkeypatch.setenv("GROQ_API_KEY", "groq-private")
    client, _ = api._get_client(provider="groq")
    assert client.api_key == "groq-private" and client.base_url == "https://api.groq.com/openai/v1"


@pytest.mark.parametrize("raw,category", [
    ('```json\n{}\n```', "LLM_JSON_PARSE_ERROR"),
    ('{"title":"a","title":"b"}', "LLM_JSON_PARSE_ERROR"),
    ('{"id":"single-puzzle"}', "LLM_INVALID_ENVELOPE"),
])
def test_blueprint_parser_does_not_repair_json_or_invent_envelopes(raw, category):
    with pytest.raises(GenerationError, match=category):
        parse_model_object(raw, blueprint_response_schema("node_connect"))


def test_exhausted_provider_retry_does_not_enter_generation_repair(provider_script, tmp_path):
    script, requests, events, _ = provider_script
    script.extend([completion(""), completion("")])
    trace = []
    with pytest.raises(ProviderError, match="PROVIDER_EMPTY_RESPONSE"):
        asyncio.run(generate_campaign(SOURCE, tmp_path, generate=api.generate, parse_json=json.loads, trace=trace))
    assert len(requests) == 2 and {e["repair_count"] for e in events} == {0}
    assert trace[-1]["provider_attempts"] == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("fault,category", [("schema", "LLM_SCHEMA_ERROR"), ("reference", "REFERENCE_ERROR")])
def test_content_failure_gets_diagnostics_and_three_repairs_not_transport_retries(provider_script, tmp_path, fault, category):
    script, requests, events, _ = provider_script
    design = blueprint()
    design["puzzles"][0]["role"] = "challenge"
    if fault == "schema":
        design["schema"] = {}
    else:
        design["puzzles"][0]["mechanics"]["goals"][0]["target"] = "missing"
    script.extend([completion(json.dumps(design)) for _ in range(3)])
    with pytest.raises(ValueError, match="tres candidatos"):
        asyncio.run(generate_campaign(SOURCE, tmp_path, generate=api.generate, parse_json=json.loads))
    assert len(requests) == 3 and [e["repair_count"] for e in events] == [0, 1, 2]
    repair = json.loads(requests[1]["messages"][1]["content"])["repair"]
    assert repair["category"] == category and repair["candidate"]
    assert not list(tmp_path.iterdir())
