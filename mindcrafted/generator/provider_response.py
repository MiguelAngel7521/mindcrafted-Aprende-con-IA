"""Provider protocol normalization and safe, actionable error categories."""
from dataclasses import dataclass
from typing import Any


class ProviderError(RuntimeError):
    def __init__(self, category, detail, *, retryable=False, status_code=None):
        super().__init__(f"{category}: {detail}")
        self.category = category
        self.retryable = retryable
        self.status_code = status_code
        self.attempts = 0


class GenerationError(ValueError):
    def __init__(self, category, detail, *, candidate=""):
        super().__init__(f"{category}: {detail}")
        self.category = category
        self.candidate = candidate


def field(value: Any, name: str, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def token_usage(raw):
    usage = field(raw, "usage")
    return {name: field(usage, name, 0) or 0 for name in
            ("prompt_tokens", "completion_tokens", "total_tokens")}


@dataclass(frozen=True)
class NormalizedModelResponse:
    text: str
    provider: str
    model: str
    response_model: str | None
    finish_reason: str | None
    usage: dict


def normalize_response(raw, *, provider, model, fixed_model=False):
    """Accept SDK objects or compatible JSON envelopes, never reasoning as content."""
    if field(raw, "error"):
        code = field(field(raw, "error"), "code")
        if not isinstance(code, int):
            raise ProviderError("PROVIDER_INVALID_RESPONSE", "Unclassified provider error envelope")
        category = ("PROVIDER_RATE_LIMIT" if code == 429 else "PROVIDER_TIMEOUT" if code == 408
                    else "PROVIDER_UPSTREAM_ERROR" if code >= 500 else "PROVIDER_HTTP_ERROR")
        raise ProviderError(category, f"Provider error envelope {code}", retryable=code in (408, 429) or code >= 500, status_code=code)
    choices = field(raw, "choices")
    if choices == []:
        raise ProviderError("PROVIDER_EMPTY_RESPONSE", "No completion choices", retryable=True)
    if not isinstance(choices, list) or not choices:
        raise ProviderError("PROVIDER_INVALID_RESPONSE", "Missing completion choices")
    message = field(choices[0], "message")
    if message is None:
        raise ProviderError("PROVIDER_INVALID_RESPONSE", "Missing assistant message")
    finish = field(choices[0], "finish_reason")
    if field(message, "refusal") or finish == "content_filter":
        raise ProviderError("PROVIDER_REFUSAL", "Provider declined the request")
    content = field(message, "content", "")
    if content is None:
        content = ""
    if isinstance(content, list):
        if any(field(block, "type") == "refusal" for block in content):
            raise ProviderError("PROVIDER_REFUSAL", "Provider declined the request")
        if any(field(block, "type") not in ("text", "output_text") or not isinstance(field(block, "text"), str) for block in content):
            raise ProviderError("PROVIDER_INVALID_RESPONSE", "Unsupported content block")
        content = "".join(field(block, "text") for block in content)
    if not isinstance(content, str):
        raise ProviderError("PROVIDER_INVALID_RESPONSE", "Assistant content must be text")
    if finish == "length":
        raise GenerationError("LLM_TRUNCATED_RESPONSE", "Completion token limit reached; shorten the candidate", candidate=content)
    if finish in ("tool_calls", "function_call"):
        raise ProviderError("PROVIDER_INVALID_RESPONSE", "Expected content, received a tool request")
    if finish == "error":
        raise ProviderError("PROVIDER_UPSTREAM_ERROR", "Completion failed upstream", retryable=True)
    if not content.strip():
        raise ProviderError("PROVIDER_EMPTY_RESPONSE", "Empty assistant content", retryable=True)
    actual = field(raw, "model")
    if (actual is not None and not isinstance(actual, str)) or (fixed_model and not actual):
        raise ProviderError("PROVIDER_INVALID_RESPONSE", "Provider did not identify the returned model")
    if fixed_model and actual and actual.removesuffix(":free") != model.removesuffix(":free"):
        raise ProviderError("PROVIDER_MODEL_MISMATCH", "Returned model differs from the pinned model")
    return NormalizedModelResponse(content, provider, model, actual, finish, token_usage(raw))
