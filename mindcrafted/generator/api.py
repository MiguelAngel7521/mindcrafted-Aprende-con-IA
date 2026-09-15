# =============================================================================
# MindCrafted — AI Game-Based Learning Studio
# =============================================================================
import asyncio
import contextvars
import hashlib
import json
import os
import sys
import time
from uuid import uuid4
from urllib.parse import urlsplit

import httpx
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

from .provider_response import GenerationError, ProviderError, field, normalize_response, token_usage
from .structured_schema import schema_hash, strict_response_schema, validate_response_text

# Default to OpenRouter; API_BASE_URL / MODEL (.env) are aliases of STUDIO_* (see server._unify_ai_env_aliases).
_OPENROUTER_BASE = (
    os.environ.get("STUDIO_AI_BASE_URL")
    or os.environ.get("API_BASE_URL")
    or "https://openrouter.ai/api/v1"
)
_DEFAULT_MODEL = (
    os.environ.get("STUDIO_MODEL")
    or os.environ.get("MODEL")
    or "google/gemini-3-flash-preview"
)

def _get_default_model() -> str:
    return (
        (os.environ.get("STUDIO_MODEL") or "").strip()
        or (os.environ.get("MODEL") or "").strip()
        or _DEFAULT_MODEL
    )


# Per-step model override: STUDIO_MODEL_<STEP> (e.g. STUDIO_MODEL_KNOWLEDGE, STUDIO_MODEL_SIM_DESIGN).
# Step names: knowledge, dialog, pixel_icons, pixel_chars, pixel_backgrounds, cover_art,
# sim_visual_objects, sim_design, sim_implement, sim_judge, sim_refine, review_batch, minigame_icons.
def get_model_for_step(step: str, model: str | None = None) -> str:
    override = (os.environ.get(f"STUDIO_MODEL_{step.upper()}") or "").strip()
    return override or (model or "").strip() or _get_default_model()

_clients: dict[str, AsyncOpenAI] = {}
_api_semaphore: asyncio.Semaphore | None = None

# When set by server (context) before running a studio job, each generate() call appends usage here for aggregation.
# Supports concurrent jobs: each task sets its own list via context.
_studio_usage_collector: list[dict] | None = None  # legacy; prefer _studio_usage_collector_ctx
_studio_usage_collector_ctx: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("studio_usage_collector", default=None)
_provider_events_ctx: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("provider_events", default=None)

PROVIDER_URLS = {"groq": "https://api.groq.com/openai/v1", "openrouter": "https://openrouter.ai/api/v1",
                 "openai": "https://api.openai.com/v1"}


def provider_config(provider=None, base_url=None):
    name = provider or os.environ.get("STUDIO_AI_PROVIDER")
    url = (base_url or PROVIDER_URLS.get(name) or os.environ.get("STUDIO_AI_BASE_URL")
           or os.environ.get("API_BASE_URL") or PROVIDER_URLS["openrouter"]).strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ProviderError("PROVIDER_CONFIG_ERROR", "Base URL must not contain credentials, query or fragment")
    inferred = {"api.groq.com": "groq", "openrouter.ai": "openrouter", "api.openai.com": "openai"}.get(parsed.hostname, "openai_compatible")
    if name in PROVIDER_URLS and inferred != "openai_compatible" and name != inferred:
        raise ProviderError("PROVIDER_CONFIG_ERROR", "Provider and base URL disagree")
    return name or inferred, url


def _get_semaphore() -> asyncio.Semaphore:
    global _api_semaphore
    if _api_semaphore is None:
        _api_semaphore = asyncio.Semaphore(2)
    return _api_semaphore


def _make_client(api_key: str, base_url: str) -> AsyncOpenAI:
    # Strip to avoid Illegal header value (e.g. trailing newline from env)
    key = (api_key or "").strip()
    url = (base_url or "").strip().rstrip("/")
    return AsyncOpenAI(
        api_key=key,
        base_url=url,
        timeout=httpx.Timeout(float(os.environ.get("STUDIO_AI_TIMEOUT", "600")), connect=30),
        max_retries=0,
    )


def _get_base_url() -> str:
    """Read base URL at runtime so env changes take effect without restart."""
    return provider_config()[1]


def _get_client(api_key: str | None = None, base_url: str | None = None, *, provider=None) -> tuple[AsyncOpenAI, str]:
    """Returns (client, cache_key) so caller can invalidate on error."""
    provider, resolved_url = provider_config(provider, base_url)
    resolved_key = (api_key or "").strip()
    if not resolved_key:
        if provider in ("groq", "openai"):
            variable = "GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY"
            resolved_key = (os.environ.get(variable) or "").strip()
            # Do not send the configured OpenRouter key to a different provider.
            if not resolved_key and provider_config()[0] == provider:
                resolved_key = (os.environ.get("API_KEY") or "").strip()
        else:
            resolved_key = (
            (os.environ.get("OPENROUTER_API_KEY_studio") or "").strip()
            or (os.environ.get("OPENROUTER_API_KEY") or "").strip()
            or (os.environ.get("API_KEY") or "").strip()
            )
        if not resolved_key:
            raise ProviderError(
                "PROVIDER_CONFIG_ERROR", "No API key for selected provider. Set GROQ_API_KEY, OPENAI_API_KEY, "
                "OPENROUTER_API_KEY or API_KEY for the configured base URL."
            )

    identity = f"{resolved_key}\0{resolved_url}".encode("utf-8")
    cache_key = hashlib.sha256(identity).hexdigest()
    if cache_key not in _clients:
        _clients[cache_key] = _make_client(resolved_key, resolved_url)
    return _clients[cache_key], cache_key


def _invalidate_client(cache_key: str):
    _clients.pop(cache_key, None)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1.5 chars per token for CJK, ~4 for Latin."""
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f')
    latin = len(text) - cjk
    return int(cjk / 1.5 + latin / 4)




def _classify_error(error):
    if isinstance(error, (ProviderError, GenerationError)):
        return error
    if isinstance(error, (APITimeoutError, httpx.TimeoutException, TimeoutError)):
        return ProviderError("PROVIDER_TIMEOUT", "Request timed out", retryable=True)
    if isinstance(error, (APIConnectionError, httpx.NetworkError)):
        return ProviderError("PROVIDER_CONNECTION_ERROR", "Provider connection failed", retryable=True)
    if isinstance(error, (APIStatusError, httpx.HTTPStatusError)):
        code = error.status_code if isinstance(error, APIStatusError) else error.response.status_code
        body = field(error, "body", {})
        provider_code = field(field(body, "error", body), "code", "")
        if code == 400 and provider_code in ("json_validate_failed", "json_validation_failed"):
            return GenerationError("LLM_SCHEMA_ERROR", "Provider rejected generated JSON against the response schema")
        category = ("PROVIDER_RATE_LIMIT" if code == 429 else "PROVIDER_TIMEOUT" if code == 408
                    else "PROVIDER_UPSTREAM_ERROR" if code >= 500 else "PROVIDER_HTTP_ERROR")
        return ProviderError(category, f"HTTP {code}", retryable=code in (408, 429) or code >= 500, status_code=code)
    return None


def _record(event):
    collector = _provider_events_ctx.get()
    if collector is not None:
        collector.append(dict(event))
    # Allowlisted metadata only: never raw response/error/header/key or prompt preview.
    print("  [provider] " + json.dumps(event, ensure_ascii=False), file=sys.stderr)


async def generate_response(
    prompt: str, system_prompt: str, *, max_tokens=4096, model=None, step=None,
    max_retries=5, api_key=None, base_url=None, provider=None, response_schema=None,
    schema_name="model_response", schema_version=None, structured_mode=None,
    fixed_model=False, generation_id=None, repair_count=0, reasoning_effort=None,
    temperature=None, top_p=None,
):
    """Normalized response; retry transport failures, never repair content here.

    max_retries retains its historical meaning: total provider attempts.
    Fixed validation pins the explicit model ahead of per-step environment overrides.
    """
    if max_retries < 1:
        raise ValueError("At least one provider attempt is required")
    model = (model or "").strip() if fixed_model else get_model_for_step(step, model) if step else (model or "").strip() or _get_default_model()
    if fixed_model and (not model or model in ("openrouter/free", "openrouter/auto", "auto", "free")):
        raise ProviderError("PROVIDER_CONFIG_ERROR", "Reproducible validation requires an explicit fixed model")
    provider, resolved_url = provider_config(provider, base_url)
    mode = (structured_mode or os.environ.get("STUDIO_STRUCTURED_OUTPUT", "strict")) if response_schema is not None else "none"
    if mode not in ("none", "strict", "best_effort", "json_mode"):
        raise ProviderError("PROVIDER_CONFIG_ERROR", "Unknown structured output mode")
    wire_schema = strict_response_schema(response_schema) if mode == "strict" else response_schema
    request = {"model": model, "max_tokens": max_tokens, "messages": [
        {"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}], "stream": False}
    if temperature is not None:
        request["temperature"] = temperature
    if top_p is not None:
        request["top_p"] = top_p
    if mode in ("strict", "best_effort"):
        request["response_format"] = {"type": "json_schema", "json_schema": {
            "name": schema_name, "strict": mode == "strict", "schema": wire_schema}}
        if provider == "openrouter":
            request["extra_body"] = {"provider": {"require_parameters": True}}
    elif mode == "json_mode":
        request["response_format"] = {"type": "json_object"}
    effort = reasoning_effort or os.environ.get("STUDIO_REASONING_EFFORT")
    if effort and effort not in ("none", "minimal", "low", "medium", "high"):
        raise ProviderError("PROVIDER_CONFIG_ERROR", "Unsupported reasoning effort")
    if provider == "openrouter" and (response_schema is not None or effort):
        reasoning = {"exclude": True}
        if effort == "none":
            reasoning["enabled"] = False
        elif effort:
            reasoning["effort"] = effort
        request.setdefault("extra_body", {})["reasoning"] = reasoning
    elif effort:
        request["reasoning_effort"] = effort
    common = {"generation_id": generation_id or str(uuid4()), "provider": provider, "model": model,
              "step": step, "schema_version": schema_version,
              "canonical_schema_hash": schema_hash(response_schema) if response_schema else None,
              "wire_schema_hash": schema_hash(wire_schema) if wire_schema else None,
              "structured_output": mode in ("strict", "best_effort"), "structured_mode": mode,
              "repair_count": repair_count, "reasoning_effort": effort,
              "temperature": temperature, "top_p": top_p}
    async with _get_semaphore():
        for attempt in range(1, max_retries + 1):
            client, cache_key = _get_client(api_key, resolved_url, provider=provider)
            start = time.monotonic()
            usage, actual, raw = {}, None, None
            try:
                raw = await client.chat.completions.create(**request)
                usage, actual = token_usage(raw), field(raw, "model")
                collector = _studio_usage_collector_ctx.get()
                if collector is None:
                    collector = _studio_usage_collector
                if collector is not None:
                    collector.append(usage)
                result = normalize_response(raw, provider=provider, model=model, fixed_model=fixed_model)
                if response_schema is not None:
                    validate_response_text(result.text, wire_schema)
            except Exception as error:
                classified = _classify_error(error)
                if classified is None:
                    raise  # Programming errors must not be hidden as transport failures.
                _record(dict(common, attempt=attempt, response_status="error", response_model=actual,
                             latency_ms=round((time.monotonic()-start)*1000), error_category=classified.category,
                             http_status=getattr(classified, "status_code", None) or (200 if raw is not None else None), usage=usage))
                if isinstance(classified, GenerationError):
                    raise classified from None
                classified.attempts = attempt
                if not classified.retryable or attempt == max_retries:
                    raise classified from None
                if classified.category == "PROVIDER_CONNECTION_ERROR":
                    _invalidate_client(cache_key)
                await asyncio.sleep(min(30, (10 if classified.category == "PROVIDER_RATE_LIMIT" else 2) * attempt))
            else:
                _record(dict(common, attempt=attempt, response_status="ok", response_model=actual,
                             latency_ms=round((time.monotonic()-start)*1000), error_category=None,
                             http_status=200, usage=usage, finish_reason=result.finish_reason))
                return result


async def generate(prompt: str, system_prompt: str, **kwargs) -> str:
    """Keep the shared V1/V2 string API; protocol details stop at this adapter."""
    response = await generate_response(prompt, system_prompt, **kwargs)
    return response.text
