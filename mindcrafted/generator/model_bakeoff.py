"""Opt-in fixed-model comparison. Selection thresholds never replace game gates."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import statistics

from dotenv import load_dotenv
import httpx

from . import api
from .prompts import WORLD_DESIGN_SYSTEM
from .provider_response import GenerationError, ProviderError
from .structured_schema import blueprint_response_schema, parse_model_object, schema_hash, strict_response_schema, validate_response_text
from .world import unique, validate_mechanics
from .world_ai_validation import digest, grounding, save, source_quality
from .world_knowledge import _evidence, _source_index, _source_metadata
from .world_pipeline import generate_campaign

THRESHOLDS = {"providerResponseRate": .90, "schemaSuccessRate": .90, "semanticSuccessRate": .80}
RATE_FIELDS = {"providerResponseRate": "providerResponse", "jsonParseRate": "jsonParse",
               "schemaSuccessRate": "schemaValid", "semanticSuccessRate": "semanticValid",
               "groundingSuccessRate": "groundingValid"}
SETTINGS = {"temperature": .2, "top_p": 1., "reasoning_effort": "medium", "max_tokens": 16384,
            "max_retries": 2, "structured_mode": "strict", "fixed_model": True}
SCHEMA_VERSION = "world-blueprint-2/node-connect-1"
REQUIRED_PARAMETERS = {"response_format", "structured_outputs", "temperature", "top_p", "reasoning", "max_tokens"}
STOP_MODEL_ERRORS = {"PROVIDER_HTTP_ERROR", "PROVIDER_MODEL_MISMATCH", "PROVIDER_CONFIG_ERROR"}


def failure_category(error):
    if isinstance(error, (ProviderError, GenerationError)):
        return error.category
    message = str(error)
    if "evidencia" in message.casefold() or "span literal" in message:
        return "GROUNDING_ERROR"
    if "meta inválida" in message:
        return "INCONSISTENT_GOAL"
    if "tipos inválidos" in message:
        return "INVALID_COMPATIBILITY"
    if "enlace inválido" in message:
        return "INVALID_NODE_RELATION"
    if "REFERENCE_ERROR" in message or "referencia" in message or "IDs duplicados" in message:
        return "REFERENCE_ERROR"
    if "EDUCATIONAL_COUPLING_ERROR" in message:
        return "WEAK_EDUCATIONAL_RELATION"
    return "SEMANTIC_VALIDATION_ERROR"


def evaluate_candidate(raw, source, canonical, wire):
    """Observe existing validators; no solver, compilation, repair or AI Judge."""
    result = {"jsonParse": False, "schemaValid": False, "semanticValid": False,
              "groundingValid": False, "failures": [], "evidence": []}
    try:
        blueprint = parse_model_object(raw, wire)
        result["jsonParse"] = True
        validate_response_text(raw, wire)
        validate_response_text(raw, canonical)
        result["schemaValid"] = True
    except GenerationError as error:
        result["jsonParse"] = error.category not in ("LLM_JSON_PARSE_ERROR",)
        result["failures"].append({"category": error.category, "diagnostic": str(error)[:6000]})
        return result
    # Reuse the package's literal evidence span resolver, independently of refs.
    try:
        index, metadata = _source_index(source), _source_metadata(source)
        for puzzle in blueprint["puzzles"]:
            for rule in puzzle["knowledge"]["requiredRules"]:
                span = _evidence(source, index, metadata, rule["evidence"])
                result["evidence"].append({"puzzleId": puzzle["id"], "ruleId": rule["id"], **span})
        result["groundingValid"] = True
    except ValueError as error:
        result["failures"].append({"category": "GROUNDING_ERROR", "diagnostic": str(error)})
    try:
        unique(blueprint["puzzles"], "blueprint")
        for puzzle in blueprint["puzzles"]:
            validate_mechanics(puzzle, source)
        result["semanticValid"] = result["groundingValid"]
    except (ValueError, TypeError, KeyError) as error:
        problem = {"category": failure_category(error), "diagnostic": str(error)[:6000]}
        if problem["category"] not in {item["category"] for item in result["failures"]}:
            result["failures"].append(problem)
    return result


def summarize(results, planned):
    rates = {key: sum(bool(row[field]) for row in results) / planned for key, field in RATE_FIELDS.items()}
    retries = sum(row["providerRetries"] for row in results)
    errors = Counter(category for row in results for category in row["providerErrors"])
    failures = Counter(item["category"] for row in results for item in row["failures"])
    latencies = [event["latency_ms"] for row in results for event in row["events"]]
    metrics = {**rates, "plannedProbes": planned, "completedProbes": len(results),
               "averageRetries": retries / max(1, len(results)), "providerErrors": dict(errors),
               "failures": dict(failures), "semanticRepairNeeded": sum(row["schemaValid"] and not row["semanticValid"] for row in results),
               "averageLatencyMs": statistics.mean(latencies) if latencies else None,
               "tokens": {key: sum(e.get("usage", {}).get(key, 0) for row in results for e in row["events"]) for key in
                          ("prompt_tokens", "completion_tokens", "total_tokens")}}
    metrics["reliabilityScore"] = round(70*rates["semanticSuccessRate"] + 15*rates["schemaSuccessRate"]
        + 10*rates["groundingSuccessRate"] + 5*rates["providerResponseRate"] - min(5, metrics["averageRetries"]), 3)
    metrics["eligible"] = len(results) == planned and all(rates[key] >= minimum for key, minimum in THRESHOLDS.items())
    return metrics


def rank(metrics):
    return tuple(metrics[key] for key in ("semanticSuccessRate", "schemaSuccessRate", "groundingSuccessRate", "providerResponseRate")) + (-metrics["averageRetries"],)


def select_finalists(rounds, limit=2):
    eligible = [model for model, data in rounds.items() if data["metrics"]["eligible"]]
    return sorted(eligible, key=lambda model: rank(rounds[model]["metrics"]), reverse=True)[:limit]


def assert_resume_contract(saved, current):
    differences = [key for key in set(saved) | set(current)
                   if key != "createdAt" and saved.get(key) != current.get(key)]
    if differences:
        raise ValueError("RESUME_CONTRACT_MISMATCH: " + ", ".join(sorted(differences)))


def model_profile(model, catalog, endpoints):
    """Catalog capabilities are claims; strict conformance is measured separately."""
    found = next((item for item in catalog["data"] if item["id"] == model), None)
    if not found or model in ("openrouter/free", "openrouter/auto"):
        raise ValueError("A model must be a fixed ID present in the live catalog")
    available = [endpoint for endpoint in endpoints["data"]["endpoints"]
                 if endpoint.get("status") == 0 and REQUIRED_PARAMETERS <= set(endpoint.get("supported_parameters", []))
                 and (endpoint.get("max_completion_tokens") or 0) >= SETTINGS["max_tokens"]]
    return {"provider": "openrouter", "model": model, "role": "blueprint",
            "supportsStructuredOutput": "structured_outputs" in found.get("supported_parameters", []),
            "supportsStrictSchema": None, "strictEvidence": "NOT_YET_MEASURED",
            "eligibleEndpoint": bool(available), "endpoints": available,
            "pricing": found.get("pricing"), "supportedParameters": found.get("supported_parameters", [])}


class Bakeoff:
    def __init__(self, source, output, *, generate=api.generate, resume=False):
        self.source, self.output, self.generate = source, output, generate
        self.resume, self.unavailable = resume, set()
        self.canonical = blueprint_response_schema("node_connect")
        self.wire = strict_response_schema(self.canonical)
        self.prompt = json.dumps({"source": source, "difficulty": "hard", "schema": self.canonical,
            "progression": "introduction", "priorKnowledge": {"skills": [], "rules": []}}, ensure_ascii=False)
        self.rate_limited = False

    async def probe(self, model, directory, generation_id, repair=None):
        events, raw, failure = [], "", None
        prompt = self.prompt
        if repair is not None:
            payload = json.loads(prompt)
            payload["repair"] = repair
            prompt = json.dumps(payload, ensure_ascii=False)
        kwargs = dict(SETTINGS, provider="openrouter", model=model, step="world_blueprint_probe",
                      response_schema=self.canonical, schema_name="world_blueprint", schema_version=SCHEMA_VERSION,
                      generation_id=generation_id, repair_count=int(repair is not None))
        if self.resume and (directory / "request.json").exists():
            # Preserve the unobserved request, without inventing a provider error
            # or turning an interrupted observation into a semantic repair.
            archive = directory / "interruptions" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            archive.mkdir(parents=True)
            (directory / "request.json").rename(archive / "request.json")
            save(archive / "status.json", {"status": "OUTCOME_UNOBSERVED", "reason": "Previous process interrupted; no result was persisted"})
        save(directory / "request.json", {"prompt": prompt, "system": WORLD_DESIGN_SYSTEM, "settings": kwargs})
        token = api._provider_events_ctx.set(events)
        try:
            raw = await self.generate(prompt, WORLD_DESIGN_SYSTEM, **kwargs)
        except (GenerationError, ProviderError) as error:
            failure = {"category": error.category, "diagnostic": str(error)[:6000]}
            raw = error.candidate if isinstance(error, GenerationError) else ""
        finally:
            api._provider_events_ctx.reset(token)
        (directory / "response.txt").write_text(raw, encoding="utf-8")
        result = evaluate_candidate(raw, self.source, self.canonical, self.wire) if raw else {
            "jsonParse": False, "schemaValid": False, "semanticValid": False, "groundingValid": False, "failures": [], "evidence": []}
        if failure:
            if failure["category"] not in {item["category"] for item in result["failures"]}:
                result["failures"].insert(0, failure)
            # A partial completion or provider failure is never a valid candidate,
            # even if its text accidentally ends with balanced JSON braces.
            result["semanticValid"] = False
        result.update(model=model, generationId=generation_id, responsePath=str(directory / "response.txt"),
            providerResponse=any(e.get("http_status") == 200 for e in events),
            providerRetries=sum(e["attempt"] > 1 for e in events), events=events,
            providerErrors=[e["error_category"] for e in events if (e.get("error_category") or "").startswith("PROVIDER_")])
        result["unobservedRequests"] = len(list((directory / "interruptions").glob("*/status.json")))
        if failure and failure["category"] == "PROVIDER_RATE_LIMIT":
            self.rate_limited = True
        save(directory / "result.json", result)
        print(json.dumps({"generation": generation_id, "model": model, "schema": result["schemaValid"],
                          "semantic": result["semanticValid"], "failures": result["failures"]}, ensure_ascii=False), flush=True)
        return result

    async def round(self, models, number, count):
        rows = {model: [] for model in models}
        disabled = set()
        # Interleave models across repetitions to reduce time-of-day bias.
        for index in range(count):
            active = []
            for model in models:
                directory = self.output / f"round-{number}" / model.replace("/", "__") / f"probe-{index+1:02}"
                if self.resume and (directory / "result.json").exists():
                    result = json.loads((directory / "result.json").read_text())
                    if result["model"] != model or not (directory / "response.txt").exists():
                        raise ValueError("RESUME_EVIDENCE_MISMATCH")
                    rows[model].append(result)
                    if any(problem["category"] in STOP_MODEL_ERRORS for problem in result["failures"]):
                        disabled.add(model)
                elif model not in disabled and model not in self.unavailable:
                    active.append(model)
            if self.rate_limited:
                break
            if not active:
                continue
            results = await asyncio.gather(*(self.probe(model,
                self.output / f"round-{number}" / model.replace("/", "__") / f"probe-{index+1:02}",
                f"round-{number}-{model.replace('/', '__')}-{index+1}") for model in active))
            for model, result in zip(active, results):
                rows[model].append(result)
                if any(problem["category"] in STOP_MODEL_ERRORS for problem in result["failures"]):
                    disabled.add(model)
            save(self.output / f"round-{number}/progress.json", {m: summarize(r, count) for m, r in rows.items()})
        return {model: {"results": result, "metrics": summarize(result, count)} for model, result in rows.items()}

    async def repairability(self, model, rounds):
        invalid = [row for data in rounds for row in data[model]["results"]
                   if row["schemaValid"] and not row["semanticValid"] and not row["providerErrors"]][:3]
        repaired = []
        for index, row in enumerate(invalid):
            candidate = Path(row["responsePath"]).read_text(encoding="utf-8")
            result = await self.probe(model, self.output / "repair" / f"case-{index+1}", f"repair-{index+1}",
                {"candidate": candidate, "errors": row["failures"], "originalGenerationId": row["generationId"]})
            repaired.append(result)
        return {"status": "MEASURED" if invalid else "NO_INVALID_SEMANTIC_OUTPUTS_AVAILABLE",
                "cases": len(invalid), "repairSuccessRate": sum(row["semanticValid"] for row in repaired) / len(invalid) if invalid else None,
                "results": repaired}

    async def campaign(self, model):
        trace, events = [], []
        directory = self.output / "campaign"

        async def captured(prompt, system, **kwargs):
            settings = dict(SETTINGS, **kwargs, provider="openrouter", model=model)
            key = f"{kwargs['step']}-{kwargs.get('repair_count', 0)}"
            save(directory / "calls" / f"{key}-request.json", {"prompt": prompt, "system": system, "settings": settings})
            try:
                raw = await self.generate(prompt, system, **settings)
            except GenerationError as error:
                (directory / "calls" / f"{key}-response.txt").write_text(error.candidate, encoding="utf-8")
                raise
            (directory / "calls" / f"{key}-response.txt").write_text(raw, encoding="utf-8")
            return raw

        token = api._provider_events_ctx.set(events)
        try:
            path = await generate_campaign(self.source, directory / "package", generate=captured,
                parse_json=json.loads, archetype="node_connect", difficulty="hard", generation_id="bakeoff-winner-campaign", trace=trace)
            package = json.loads((directory / "package/game.pkg.json").read_text())
            save(directory / "grounding.json", grounding(package))
            result = {"status": "APPROVED", "path": path}
        except (ProviderError, ValueError) as error:
            result = {"status": "NOT YET APPROVED", "diagnostic": str(error)[:6000]}
        finally:
            api._provider_events_ctx.reset(token)
            save(directory / "trace.json", trace)
            save(directory / "provider-events.json", events)
        return result


async def run(args):
    if not 3 <= len(set(args.models)) == len(args.models) <= 6:
        raise ValueError("Choose 3–6 distinct fixed models")
    resume = getattr(args, "resume_round_one", False)
    if args.output.exists() and any(args.output.iterdir()) and not resume:
        raise ValueError("Use an empty output directory to preserve evidence")
    source = args.source.read_text(encoding="utf-8")
    if source_quality(source)["status"] != "PASS":
        raise ValueError("SOURCE_TOO_WEAK_FOR_NODE_CONNECT")
    runner = Bakeoff(source, args.output, resume=resume)
    registry_hash = digest(Path("courses.json"))
    protocol = {"version": "model-bakeoff-1", "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceHash": hashlib.sha256(source.encode()).hexdigest(), "sourceQuality": source_quality(source),
        "promptHash": hashlib.sha256((WORLD_DESIGN_SYSTEM + '\n' + runner.prompt).encode()).hexdigest(),
        "canonicalSchemaHash": schema_hash(runner.canonical), "wireSchemaHash": schema_hash(runner.wire),
        "semanticValidatorHash": digest(Path(__file__).with_name("world.py")), "thresholds": THRESHOLDS,
        "round1Probes": 5, "round2Probes": 10, "settings": SETTINGS, "coursesRegistryHash": registry_hash}
    metadata_dir = args.output
    if resume:
        assert_resume_contract(json.loads((args.output / "protocol.json").read_text()), protocol)
        old_profiles = json.loads((args.output / "profiles.json").read_text())
        if args.models != [profile["model"] for profile in old_profiles]:
            raise ValueError("RESUME_CONTRACT_MISMATCH: models")
        if any((args.output / name).exists() for name in ("summary.json", "round-2", "repair", "campaign")):
            raise ValueError("Resume supports interrupted first rounds only; later stages must not be replayed")
        metadata_dir = args.output / ("resume-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
        catalog = response.json()
        profiles = []
        for model in args.models:
            response = await client.get(f"https://openrouter.ai/api/v1/models/{model}/endpoints")
            response.raise_for_status()
            endpoints = response.json()
            profile = model_profile(model, catalog, endpoints)
            profiles.append(profile)
            save(metadata_dir / "capabilities" / (model.replace("/", "__") + ".json"), endpoints)
    save(metadata_dir / "catalog.json", catalog)
    save(metadata_dir / "profiles.json", profiles)
    save(metadata_dir / "protocol.json", protocol)
    save(metadata_dir / "canonical-schema.json", runner.canonical)
    save(metadata_dir / "wire-schema.json", runner.wire)
    (metadata_dir / "source.txt").write_text(source, encoding="utf-8")
    runner.unavailable = {profile["model"] for profile in profiles if not profile["eligibleEndpoint"]}
    models = [profile["model"] for profile in (old_profiles if resume else profiles) if profile["eligibleEndpoint"]]
    first = await runner.round(models, 1, 5)
    finalists = select_finalists(first)
    second = await runner.round(finalists, 2, 10) if finalists and not runner.rate_limited else {}
    winners = select_finalists(second, 1)
    selected = winners[0] if winners else None
    repair = await runner.repairability(selected, [first, second]) if selected else {"status": "NOT_RUN_NO_WINNER"}
    campaign = await runner.campaign(selected) if selected and not runner.rate_limited else {"status": "NOT YET APPROVED", "reason": "No qualified winner or provider limit"}
    result = {"status": "APPROVED" if selected else "REJECTED", "selectedModel": selected,
              "round1": first, "finalists": finalists, "round2": second, "repairability": repair, "campaign": campaign,
              "unobservedRequests": sum(row.get("unobservedRequests", 0) for data in first.values() for row in data["results"]),
              "rateLimited": runner.rate_limited, "coursesRegistryUnchanged": digest(Path("courses.json")) == registry_hash}
    save(args.output / "summary.json", result)
    if not result["coursesRegistryUnchanged"]:
        raise RuntimeError("courses.json changed during the bake-off")
    print(json.dumps({key: result[key] for key in ("status", "selectedModel", "finalists", "campaign")}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--resume-round-one", action="store_true", help="Keep completed probes and resume only missing first-round observations")
    args = parser.parse_args()
    load_dotenv()
    os.environ["STUDIO_AI_TIMEOUT"] = "120"
    result = asyncio.run(run(args))
    if result["status"] != "APPROVED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
