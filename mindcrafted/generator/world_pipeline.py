"""Bounded design → compile → deterministic gate → AI judge → repair pipeline."""

import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

from .prompts import WORLD_DESIGN_SYSTEM, WORLD_JUDGE_SYSTEM
from .world import compile_world, schema_check, unique, validate_mechanics, world_hash
from .world_package import CHECKS, JUDGE_SCHEMA, check_judge, make_package, quality_gate, write_world_package
from .provider_response import GenerationError, ProviderError
from .structured_schema import blueprint_response_schema, parse_model_object, schema_hash


def content_error_category(error, stage):
    if isinstance(error, GenerationError):
        return error.category
    for category in ("UNSOLVABLE", "REFERENCE_ERROR", "EDUCATIONAL_COUPLING_ERROR", "RANDOM_SUCCESS_ERROR",
                     "DIFFICULTY_ERROR", "WORLD_INTEGRATION_ERROR", "PERSISTENCE_ERROR"):
        if category in str(error):
            return category
    return {"schema": "LLM_SCHEMA_ERROR", "semantic": "SEMANTIC_VALIDATION_ERROR",
            "compiler": "COMPILATION_ERROR", "quality_gate": "DETERMINISTIC_GATE_FAILURE",
            "judge": "AI_JUDGE_REJECTION"}.get(stage, "GENERATION_CONTENT_ERROR")


async def generate_campaign(source, output_dir, *, generate, parse_json, chunk_id="", title="", difficulty="normal", previous_context=None, require_boss=False,
                            archetype=None, generation_id=None, trace=None):
    """Generate one source-grounded region; course orchestration connects regions."""
    if not isinstance(source, str) or not 60 <= len(source.strip()) <= 60000:
        raise ValueError("El mundo necesita entre 60 y 60000 caracteres de material educativo")
    previous_context = deepcopy(previous_context or {"skills": [], "rules": []})
    original_hash = hashlib.sha256(source.encode()).hexdigest()
    retained = []
    for rule in previous_context.get("rules", []):
        quotes = list(dict.fromkeys(e["quote"] for e in rule.get("evidence", []) if e["quote"] not in source))
        extra = "\n\nMaterial de repaso:\n" + "\n".join(quotes) if quotes else ""
        if len(source) + len(extra) <= 60000:
            source += extra
            retained.append(rule)
        else:
            previous_context["truncated"] = True
    previous_context["rules"] = retained
    previous_context["skills"] = list(dict.fromkeys(r["skill"] for r in retained))
    generation_id = generation_id or str(uuid4())
    response_schema = blueprint_response_schema(archetype)
    schema_version = "world-blueprint-2" + ("/node-connect-1" if archetype == "node_connect" else "")

    def record(stage, status, attempt, **details):
        event = {"generation_id": generation_id, "stage": stage, "status": status,
                 "attempt": attempt + 1, "repair_count": attempt, "schema_version": schema_version,
                 "canonical_schema_hash": schema_hash(response_schema), **details}
        if trace is not None:
            trace.append(event)

    request = {"title": title, "difficulty": difficulty, "source": source, "schema": response_schema,
               "priorKnowledge": previous_context, "progression": "boss" if require_boss else "transfer" if previous_context.get("skills") else "introduction"}
    repair = None
    for attempt in range(3):
        print(f"  [{attempt + 1}/3] Diseñando una región integrada al mundo...", file=sys.stderr)
        payload = dict(request)
        if repair:
            payload["repair"] = repair
        raw = ""
        stage = "provider"
        try:
            raw = await generate(json.dumps(payload, ensure_ascii=False), WORLD_DESIGN_SYSTEM,
                                 max_tokens=8500, step="world_blueprint", max_retries=2,
                                 response_schema=response_schema, schema_name="world_blueprint", schema_version=schema_version,
                                 generation_id=generation_id, repair_count=attempt)
            record("provider", "pass", attempt)
            stage = "parse"
            blueprint = parse_model_object(raw, response_schema)
            record("json_parse", "pass", attempt)
            stage = "schema"
            schema_check(blueprint, response_schema)
            record(stage, "pass", attempt)
            stage = "semantic"
            unique(blueprint["puzzles"], "blueprint")
            for puzzle in blueprint["puzzles"]:
                validate_mechanics(puzzle, source)
            record(stage, "pass", attempt)
            stage = "compiler"
            world = compile_world(blueprint, source, difficulty=difficulty, prior_skills=previous_context.get("skills", []))
            if require_boss and world["puzzles"][-1].get("role") != "boss":
                raise ValueError("La última región necesita un boss que combine habilidades anteriores")
            record("compiler", "pass", attempt)
            record("solver", "pass", attempt)
            stage = "quality_gate"
            report = await asyncio.to_thread(quality_gate, world, source)
            if not all(report["checks"].get(key) is True for key in CHECKS):
                raise ValueError("; ".join(report["errors"]) or "Pruebas deterministas incompletas")
            record(stage, "pass", attempt, checks=report["checks"], solutions=report["solutions"], e2e=report["e2e"])
            stage = "judge"
            judge_raw = await generate(json.dumps({"source": source, "world": world, "tests": report["checks"]}, ensure_ascii=False),
                                       WORLD_JUDGE_SYSTEM, max_tokens=2200, step="world_judge", max_retries=2,
                                       response_schema=JUDGE_SCHEMA, schema_name="world_judge", schema_version="world-judge-1",
                                       generation_id=generation_id, repair_count=attempt)
            judge = parse_model_object(judge_raw, JUDGE_SCHEMA)
            schema_check(judge, JUDGE_SCHEMA)
            if not check_judge(judge):
                raise ValueError("Juez <85 o rechazo: " + json.dumps(judge, ensure_ascii=False))
            record(stage, "pass", attempt, judge=judge)
            report["judge"] = judge
            report["approved"] = True
            package = make_package(world, source, chunk_id, title or None)
            package["config"]["sourceMaterialHash"] = original_hash
            print("  [world] schema, world graph, solver, educación, runtime, E2E y juez aprobados", file=sys.stderr)
            path = write_world_package(package, source, report, output_dir)
            record("published", "pass", attempt, path=path)
            return path
        except ProviderError as error:
            record(stage, "fail", attempt, error_category=error.category, errors=str(error), provider_attempts=error.attempts)
            # The adapter has exhausted transport retries, or the provider rejected
            # the request. Another content repair would repeat the same failure.
            raise
        except (ValueError, TypeError, KeyError) as error:
            category = content_error_category(error, stage)
            candidate = error.candidate if isinstance(error, GenerationError) and stage == "provider" else raw
            repair = {"candidate": candidate[:40000], "errors": str(error)[:6000], "category": category, "stage": stage}
            record("solver" if category == "UNSOLVABLE" else stage, "fail", attempt, error_category=category, errors=str(error)[:6000])
            print(f"  [world] Candidato rechazado; reparación {attempt + 1}/3: {str(error)[:500]}", file=sys.stderr)
    return await build_safe_fallback(source, output_dir, repair["errors"], require_boss=require_boss)


async def build_safe_fallback(source, output_dir, reason, *, require_boss=False):
    """Only reuse a previously approved, source-identical world, re-probed today."""
    path = Path(output_dir) / "game.pkg.json"
    if path.exists():
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
            if require_boss and package["world"]["puzzles"][-1].get("role") != "boss":
                raise ValueError("El fallback no contiene el boss requerido")
            source_hash = hashlib.sha256(source.encode()).hexdigest()
            if package.get("config", {}).get("generationMode") == "world" and package["config"].get("sourceHash") == source_hash:
                old = package.get("quality", {})
                if old.get("approved") is True and old.get("worldHash") == world_hash(package["world"]) and check_judge(old.get("judge")):
                    report = await asyncio.to_thread(quality_gate, package["world"], source, judge=old["judge"])
                    if report["approved"]:
                        report["fallback"] = "previously_approved_source_identical"
                        print("  [world] Se reutiliza el mundo aprobado de estos mismos apuntes tras repetir sus pruebas.", file=sys.stderr)
                        return write_world_package(package, source, report, output_dir)
        except (ValueError, KeyError, TypeError):
            pass
    raise ValueError("No se publicó un mundo: tres candidatos rechazados y no existe un fallback aprobado para este material. " + reason)
