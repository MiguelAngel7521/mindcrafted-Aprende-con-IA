"""Server-side provider configuration must not leak its credential."""
import pytest
from fastapi import HTTPException

from mindcrafted import server


def test_custom_provider_requires_explicit_byok_key(monkeypatch):
    monkeypatch.setattr(server, "API_KEY", "server-secret")
    monkeypatch.setattr(server, "API_BASE_URL", "https://configured.test/v1")

    with pytest.raises(HTTPException, match="clave BYOK"):
        server._resolve_ai_config({"base_url": "https://attacker.test/v1"})


def test_custom_provider_can_use_explicit_byok_key(monkeypatch):
    monkeypatch.setattr(server, "API_KEY", "server-secret")
    monkeypatch.setattr(server, "API_BASE_URL", "https://configured.test/v1")

    api_key, base_url, model = server._resolve_ai_config({
        "api_key": "student-key",
        "base_url": "https://student-provider.test/v1/",
        "model": "student-model",
    })

    assert (api_key, base_url, model) == (
        "student-key", "https://student-provider.test/v1", "student-model"
    )


def test_configured_provider_can_use_server_key(monkeypatch):
    monkeypatch.setattr(server, "API_KEY", "server-secret")
    monkeypatch.setattr(server, "API_BASE_URL", "https://configured.test/v1")

    api_key, base_url, model = server._resolve_ai_config({})

    assert api_key == "server-secret"
    assert base_url == "https://configured.test/v1"
    assert model == server.MODEL
