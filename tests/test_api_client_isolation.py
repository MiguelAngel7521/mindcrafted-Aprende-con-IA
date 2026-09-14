"""Request credentials and selected models must survive concurrent BYOK jobs."""
import asyncio
import re
from types import SimpleNamespace

import pytest

from mindcrafted.generator import api, pipeline


@pytest.fixture
def fake_clients(monkeypatch):
    for name in ("OPENROUTER_API_KEY_studio", "OPENROUTER_API_KEY", "API_KEY",
                 "STUDIO_AI_BASE_URL", "API_BASE_URL", "STUDIO_MODEL", "MODEL",
                 "STUDIO_MODEL_KNOWLEDGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api, "_clients", {})
    monkeypatch.setattr(api, "_api_semaphore", None)
    monkeypatch.setattr(api, "_DEFAULT_MODEL", "fallback-model")
    created = []

    def make_client(api_key, base_url):
        calls = []

        async def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=None)

        client = SimpleNamespace(api_key=api_key, base_url=base_url, calls=calls,
                                 chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        created.append(client)
        return client

    monkeypatch.setattr(api, "_make_client", make_client)
    return created


def test_full_byok_credentials_are_isolated_and_cache_keys_hide_secrets(fake_clients):
    first_key, second_key = "prefix01-first-private-key", "prefix01-second-private-key"
    first, first_token = api._get_client(first_key, "https://provider.test/v1")
    second, second_token = api._get_client(second_key, "https://provider.test/v1")
    assert first is not second
    assert first.api_key == first_key and second.api_key == second_key
    assert first_token != second_token
    assert api._get_client(first_key, "https://provider.test/v1") == (first, first_token)
    assert api._get_client(second_key, "https://provider.test/v1") == (second, second_token)
    assert len(fake_clients) == 2
    for token in api._clients:
        assert re.fullmatch(r"[0-9a-f]{64}", token)
        assert first_key not in token and second_key not in token and "prefix01" not in token


def test_normalized_credentials_and_url_share_only_the_same_client(fake_clients):
    first, token = api._get_client("  complete-key\n", " https://provider.test/v1/ ")
    assert first.api_key == "complete-key"
    assert first.base_url == "https://provider.test/v1"
    assert api._get_client("complete-key", "https://provider.test/v1") == (first, token)
    different, different_token = api._get_client("complete-key", "https://other.test/v1")
    assert different is not first and different_token != token
    assert len(fake_clients) == 2


def test_environment_credential_and_url_rotation_do_not_reuse_stale_clients(monkeypatch, fake_clients):
    monkeypatch.setenv("API_KEY", "environment-key-first")
    monkeypatch.setenv("API_BASE_URL", "https://first.test/v1")
    first, first_token = api._get_client()
    monkeypatch.setenv("API_KEY", "environment-key-second")
    second, second_token = api._get_client()
    monkeypatch.setenv("API_BASE_URL", "https://second.test/v1")
    third, third_token = api._get_client()
    assert len({first_token, second_token, third_token}) == 3
    assert first is not second and second is not third
    assert second.api_key == third.api_key == "environment-key-second"
    assert second.base_url == "https://first.test/v1" and third.base_url == "https://second.test/v1"
    monkeypatch.setenv("API_KEY", "environment-key-first")
    monkeypatch.setenv("API_BASE_URL", "https://first.test/v1")
    assert api._get_client() == (first, first_token)


def test_explicit_url_is_honored_with_environment_credentials(monkeypatch, fake_clients):
    monkeypatch.setenv("OPENROUTER_API_KEY_studio", "studio-environment-key")
    monkeypatch.setenv("API_KEY", "lower-priority-key")
    monkeypatch.setenv("STUDIO_AI_BASE_URL", "https://environment.test/v1")
    explicit, token = api._get_client(base_url="https://explicit.test/v1/")
    assert explicit.api_key == "studio-environment-key"
    assert explicit.base_url == "https://explicit.test/v1"
    assert api._get_client("studio-environment-key", "https://explicit.test/v1") == (explicit, token)
    default, default_token = api._get_client()
    assert default.base_url == "https://environment.test/v1"
    assert default is not explicit and default_token != token


def test_invalidation_only_replaces_the_matching_identity(fake_clients):
    first, first_token = api._get_client("prefix01-first-key")
    second, second_token = api._get_client("prefix01-second-key")
    api._invalidate_client(first_token)
    replacement, replacement_token = api._get_client("prefix01-first-key")
    assert replacement is not first and replacement_token == first_token
    assert api._get_client("prefix01-second-key") == (second, second_token)


def test_missing_credentials_fail_before_creating_a_client(fake_clients):
    with pytest.raises(RuntimeError, match="No API key"):
        api._get_client()
    assert fake_clients == [] and api._clients == {}


@pytest.mark.parametrize("step,explicit,override,default,expected", [
    ("knowledge", "requested-model", "stage-model", "global-model", "stage-model"),
    ("knowledge", "requested-model", None, "global-model", "requested-model"),
    ("knowledge", "requested-model", "", "global-model", "requested-model"),
    ("knowledge", None, None, "global-model", "global-model"),
    ("knowledge", None, None, None, "fallback-model"),
    (None, "requested-model", "stage-model", "global-model", "requested-model"),
    (None, None, None, "global-model", "global-model"),
])
def test_model_priority_preserves_explicit_selection(monkeypatch, fake_clients, capsys,
                                                    step, explicit, override, default, expected):
    if default is not None:
        monkeypatch.setenv("STUDIO_MODEL", default)
    if override is not None:
        monkeypatch.setenv("STUDIO_MODEL_KNOWLEDGE", override)
    key = "synthetic-private-api-key"
    result = asyncio.run(api.generate("sample", "system", api_key=key, base_url="https://provider.test/v1",
                                      step=step, model=explicit, max_retries=1))
    assert result == "ok"
    assert fake_clients[0].calls[0]["model"] == expected
    assert key not in capsys.readouterr().err


@pytest.mark.parametrize("stage_override", [None, "stage-model"])
def test_bound_pipeline_wrapper_keeps_credentials_url_and_model(monkeypatch, fake_clients, stage_override):
    monkeypatch.setenv("API_KEY", "environment-private-key")
    monkeypatch.setenv("STUDIO_AI_BASE_URL", "https://environment.test/v1")
    monkeypatch.setenv("STUDIO_MODEL", "global-model")
    if stage_override:
        monkeypatch.setenv("STUDIO_MODEL_KNOWLEDGE", stage_override)
    bound = pipeline._bind_api_config(None, "https://request.test/v1", "request-model")

    async def run():
        assert await bound("sample", "system", step="knowledge", max_retries=1) == "ok"
        assert await bound("sample", "system", step="knowledge", model="call-model", max_retries=1) == "ok"

    asyncio.run(run())
    assert len(fake_clients) == 1
    client = fake_clients[0]
    assert client.api_key == "environment-private-key"
    assert client.base_url == "https://request.test/v1"
    assert [call["model"] for call in client.calls] == [stage_override or "request-model", stage_override or "call-model"]
