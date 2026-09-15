"""Derived API schemas; the Pydantic World V2 contract remains authoritative."""
from copy import deepcopy
import hashlib
import json
from jsonschema import Draft202012Validator

from .world_schema import BLUEPRINT_SCHEMA
from .provider_response import GenerationError


def parse_model_object(raw, schema):
    """Strict parsing: no JSON repair, fence removal or inferred wrapper."""
    def distinct(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON property: {key}")
            result[key] = value
        return result

    def non_finite(_):
        raise ValueError("Non-finite JSON number")

    try:
        value = json.loads(raw, object_pairs_hook=distinct, parse_constant=non_finite)
    except (ValueError, TypeError) as error:
        raise GenerationError("LLM_JSON_PARSE_ERROR", str(error), candidate=raw or "") from error
    if not isinstance(value, dict) or not set(schema.get("required", ())).issubset(value):
        raise GenerationError("LLM_INVALID_ENVELOPE", "Response does not match the requested root object", candidate=raw)
    return value


def validate_response_text(raw, schema):
    value = parse_model_object(raw, schema)
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, error.path))}: {error.message}" for error in errors[:6])
        raise GenerationError("LLM_SCHEMA_ERROR", detail, candidate=raw)
    return value


def schema_hash(schema):
    return hashlib.sha256(json.dumps(schema, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def blueprint_response_schema(archetype=None, *, puzzle_only=False):
    schema = deepcopy(BLUEPRINT_SCHEMA)
    definitions = schema["$defs"]
    if archetype:
        mechanics = definitions["BlueprintPuzzle"]["properties"]["mechanics"]
        reference = mechanics["discriminator"]["mapping"].get(archetype)
        if not reference:
            raise ValueError(f"Unknown archetype: {archetype}")
        definitions["BlueprintPuzzle"]["properties"]["mechanics"] = {"$ref": reference}
        schema["properties"]["puzzles"]["minItems"] = 1
        schema["properties"]["puzzles"]["maxItems"] = 1
    if puzzle_only:
        schema = dict(deepcopy(definitions["BlueprintPuzzle"]), **{"$defs": definitions})
    # Remove unreferenced archetypes so the request only carries its actual contract.
    used = set()

    def references(value):
        if isinstance(value, list):
            for item in value:
                references(item)
        elif isinstance(value, dict):
            if "$ref" in value:
                name = value["$ref"].removeprefix("#/$defs/")
                if name not in used:
                    used.add(name)
                    references(definitions[name])
            for key, item in value.items():
                if key != "$defs":
                    references(item)

    references(schema)
    schema["$defs"] = {name: value for name, value in definitions.items() if name in used}
    return schema


def strict_response_schema(schema):
    """Preserve constraints; close objects and require existing optional fields.

    Pydantic's discriminator unions are disjoint: converting those oneOfs to
    anyOf is equivalent. Never strip bounds/patterns or rewrite Blueprint data.
    """
    root = deepcopy(schema)
    definitions = root.get("$defs", {})

    def adapt(value):
        if isinstance(value, list):
            return [adapt(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = dict(value)
        if "oneOf" in result:
            discriminator = result.get("discriminator", {}).get("propertyName")
            variants = [definitions[item["$ref"].removeprefix("#/$defs/")] if "$ref" in item else item for item in result["oneOf"]]
            tags = [item.get("properties", {}).get(discriminator, {}).get("const") for item in variants]
            if not discriminator or None in tags or len(set(tags)) != len(tags):
                raise ValueError("Strict API schema requires disjoint discriminated unions")
            result["anyOf"] = result.pop("oneOf")
        result.pop("discriminator", None)
        result.pop("default", None)
        if "const" in result:
            result["enum"] = [result.pop("const")]
        if result.get("type") == "object":
            if result.get("additionalProperties") is not False:
                raise ValueError("Strict API schema requires closed objects")
            result["required"] = list(result.get("properties", {}))
        return {key: adapt(item) for key, item in result.items()}

    return adapt(root)
