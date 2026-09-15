"""Opt-in real-provider validation. Never run live calls from the unit test suite."""
import argparse
import asyncio
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from jsonschema import Draft202012Validator

from . import api
from .prompts import WORLD_DESIGN_SYSTEM
from .provider_response import GenerationError, ProviderError
from .structured_schema import blueprint_response_schema, parse_model_object, schema_hash, strict_response_schema, validate_response_text
from .world import validate_mechanics
from .world_pipeline import generate_campaign


_RELATION_RE = re.compile(
    r"\b(?:depende(?:n)?\s+(?:únicamente\s+)?de|conecta(?:do|n)?\s+(?:con|a)|"
    r"relacion(?:a|es?)\s+(?:con|entre)|recibe|extrae(?:n)?|produce|ajusta|"
    r"permite|requiere|utiliza|aprende\s+con|encuentra|reconoce|impulsa|"
    r"contiene|incluye)\b",
    re.IGNORECASE,
)


def source_quality(source):
    """Measure whether source text has enough grounded relations for node_connect."""
    segments = [re.sub(r"\s+", " ", item).strip(" •\t") for item in re.split(r"[\n.;]+", source)]
    segments = [item for item in segments if len(item) >= 15]
    related = [item for item in segments if _RELATION_RE.search(item) or "→" in item or "->" in item]
    concepts = set()
    for item in related:
        match = _RELATION_RE.search(item)
        if match:
            left = item[:match.start()].split()[-5:]
            right = item[match.end():].split()[:5]
            if left:
                concepts.add(" ".join(left).casefold())
            if right:
                concepts.add(" ".join(right).casefold())
        else:
            concepts.update(part.strip().casefold() for part in item.split("→") if part.strip())
    relationship_count = len(related)
    grounded_facts = len(segments)
    coverage = relationship_count / max(1, grounded_facts)
    status = "PASS" if relationship_count >= 2 and len(concepts) >= 3 else "SOURCE_TOO_WEAK_FOR_NODE_CONNECT"
    return {"status": status, "conceptCount": len(concepts), "relationshipCount": relationship_count,
            "groundedFacts": grounded_facts, "usableNodeRelations": relationship_count,
            "sourceCoverage": round(coverage, 3)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def grounding(package):
    result = []
    for puzzle in package["world"]["puzzles"]:
        mechanics = puzzle["mechanics"]
        for rule in puzzle["knowledge"]["requiredRules"]:
            constraints = [r for r in mechanics["connectionRules"] if r["ruleId"] == rule["id"]]
            goals = [r for r in mechanics["goals"] if r["ruleId"] == rule["id"]]
            kinds = {pair[key] for c in constraints if c["kind"] == "compatible" for pair in c["allowed"] for key in ("sourceKind", "targetKind")}
            ids = {c["node"] for c in constraints if c["kind"] == "degree"} | {g[key] for g in goals for key in ("source", "target")}
            nodes = [n for n in mechanics["nodes"] if n["kind"] in kinds or n["id"] in ids or any(c["kind"] == "acyclic" for c in constraints)]
            result.append({"puzzleId": puzzle["id"], "rule": rule, "constraints": constraints,
                           "requiredPaths": goals, "affectedNodesAndRoles": nodes})
    return {"sourceHash": package["config"]["sourceHash"], "bindings": result,
            "knowledgeGraph": package["knowledgeGraph"]}


async def validate_runs(args):
    source = args.source.read_text(encoding="utf-8")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Use a new output directory; validation evidence must not be overwritten")
    args.output.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    source_metrics = source_quality(source)
    canonical = blueprint_response_schema("node_connect")
    wire = strict_response_schema(canonical) if args.mode == "strict" else canonical
    registry = Path("courses.json")
    before = digest(registry)
    config = {"provider": args.provider, "model": args.model, "structured_mode": args.mode,
              "source": str(args.source), "sourceHash": source_hash, "characters": len(source),
              "sourceQuality": source_metrics,
              "canonicalSchemaHash": schema_hash(canonical), "wireSchemaHash": schema_hash(wire),
              "schemaVersion": "world-blueprint-2/node-connect-1",
              "difficulty": args.difficulty, "requestedRuns": args.runs, "coursesRegistryHash": before,
              "reasoningEffort": args.reasoning_effort, "timeoutSeconds": args.timeout}
    save(args.output / "configuration.json", config)
    save(args.output / "canonical-schema.json", canonical)
    save(args.output / "api-schema.json", wire)
    (args.output / "source.txt").write_text(source, encoding="utf-8")
    events, runs = [], []
    collector = api._provider_events_ctx.set(events)
    bound = partial(api.generate, provider=args.provider, model=args.model, fixed_model=True,
                    structured_mode=args.mode, reasoning_effort=args.reasoning_effort)

    async def captured(directory, prompt, system, **kwargs):
        key = f"{kwargs['step']}-{kwargs.get('repair_count', 0)}"
        canonical = kwargs.get("response_schema")
        mode = kwargs.get("structured_mode") or args.mode
        wire = strict_response_schema(canonical) if canonical is not None and mode == "strict" else canonical
        save(directory / f"{key}-request.json", {"prompt": json.loads(prompt), "system": system,
             "provider": args.provider, "model": args.model, "structured_mode": mode,
             "canonical_schema": canonical, "wire_schema": wire,
             "canonical_schema_hash": schema_hash(canonical) if canonical else None,
             "wire_schema_hash": schema_hash(wire) if wire else None})
        try:
            raw = await bound(prompt, system, **kwargs)
        except GenerationError as error:
            if error.candidate:
                (directory / f"{key}-response.txt").write_text(error.candidate, encoding="utf-8")
            raise
        finally:
            save(args.output / "provider-events.json", events)
        (directory / f"{key}-response.txt").write_text(raw, encoding="utf-8")
        return raw

    probe_results = []
    try:
        for index in range(args.probes):
            probe_dir = args.output / f"probe-{index + 1:02}"
            generation_id = f"probe-{source_hash[:12]}-{index + 1}"
            result = {"probe": index + 1, "status": "rejected", "jsonParse": False,
                      "schemaValid": False, "semanticValid": False, "category": None}
            try:
                probe_raw = await captured(probe_dir, json.dumps({"source": source, "difficulty": args.difficulty,
                     "schema": canonical, "progression": "introduction", "priorKnowledge": {"skills": [], "rules": []}}, ensure_ascii=False),
                     WORLD_DESIGN_SYSTEM, step="world_blueprint_probe", max_tokens=8500, max_retries=2,
                     response_schema=canonical, schema_name="world_blueprint", schema_version=config["schemaVersion"],
                     generation_id=generation_id, repair_count=0)
                blueprint = parse_model_object(probe_raw, wire)
                result["jsonParse"] = True
                errors = sorted(Draft202012Validator(wire).iter_errors(blueprint), key=lambda error: str(error.path))
                if errors:
                    detail = "; ".join(f"{'/'.join(map(str, error.path))}: {error.message}" for error in errors[:6])
                    raise GenerationError("LLM_SCHEMA_ERROR", detail, candidate=probe_raw)
                result["schemaValid"] = True
                for puzzle in blueprint["puzzles"]:
                    validate_mechanics(puzzle, source)
                result["semanticValid"] = True
                result["status"] = "pass"
                save(probe_dir / "blueprint.json", blueprint)
            except (ProviderError, GenerationError, ValueError, TypeError, KeyError) as error:
                result.update(category=getattr(error, "category", None) or "SEMANTIC_VALIDATION_ERROR",
                              error=str(error)[:6000])
            own_events = [event for event in events if event.get("generation_id") == generation_id]
            result["providerResponse"] = any(event.get("http_status") == 200 for event in own_events)
            result["providerCalls"] = len(own_events)
            result["providerRetries"] = sum(event.get("attempt", 1) > 1 for event in own_events)
            save(probe_dir / "result.json", result)
            probe_results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        total_probes = max(1, len(probe_results))
        rates = {name: round(sum(bool(result.get(name)) for result in probe_results) / total_probes, 3)
                 for name in ("providerResponse", "jsonParse", "schemaValid", "semanticValid")}
        probe = {"status": "pass" if all(rates[name] >= 0.8 for name in ("providerResponse", "schemaValid", "semanticValid")) else "rejected",
                 "structuredMode": args.mode, "requestedProbes": args.probes, "results": probe_results,
                 "providerResponseRate": rates["providerResponse"], "schemaSuccessRate": rates["schemaValid"],
                 "semanticSuccessRate": rates["semanticValid"], "sourceQuality": source_metrics}
        save(args.output / "probe/result.json", probe)
        # Never run the campaign until the isolated structured response passes.
        if probe["status"] == "pass" and args.command == "run" and source_metrics["status"] == "PASS":
            for index in range(args.runs):
                directory = args.output / f"run-{index + 1:02}"
                trace = []
                first_event = len(events)
                result = {"run": index + 1, "status": "rejected", "errorCategory": None}
                try:
                    path = await generate_campaign(source, directory / "campaign", generate=partial(captured, directory / "calls"),
                         parse_json=json.loads, difficulty=args.difficulty, archetype="node_connect", chunk_id="node_connect",
                         generation_id=f"{source_hash[:12]}-{index + 1}", trace=trace)
                    package = json.loads((directory / "campaign/game.pkg.json").read_text())
                    save(directory / "grounding.json", grounding(package))
                    result.update(status="approved", playablePackage=path)
                except (ProviderError, ValueError, KeyError, TypeError, OSError) as error:
                    result.update(errorCategory=getattr(error, "category", None) or (trace[-1].get("error_category") if trace else "UNKNOWN"),
                                  error=str(error)[:6000])
                own_events = events[first_event:]
                response_texts = [p.read_text() for p in (directory / "calls").glob("world_blueprint-*-response.txt")]
                parsed, valid = False, False
                for raw in response_texts:
                    try:
                        json.loads(raw)
                        parsed = True
                        validate_response_text(raw, wire)
                        valid = True
                    except (ValueError, GenerationError):
                        continue
                stages = {item["stage"] for item in trace if item["status"] == "pass"}
                result.update(providerResponse=any(e["response_status"] == "ok" and e["step"] == "world_blueprint" for e in own_events),
                    jsonParse=parsed, schemaValid=valid, semanticValid="semantic" in stages, solverValid="solver" in stages,
                    qualityGate="quality_gate" in stages, judgeApproved="judge" in stages, published="published" in stages,
                    repairs=max((e["repair_count"] for e in own_events), default=0), providerCalls=len(own_events),
                    providerRetries=sum(e["attempt"] > 1 for e in own_events))
                save(directory / "trace.json", trace)
                save(directory / "result.json", result)
                runs.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if result["errorCategory"] in ("PROVIDER_RATE_LIMIT", "PROVIDER_HTTP_ERROR", "PROVIDER_CONFIG_ERROR", "PROVIDER_MODEL_MISMATCH"):
                    break
    finally:
        api._provider_events_ctx.reset(collector)
        save(args.output / "provider-events.json", events)
    after = digest(registry)
    if before != after:
        raise RuntimeError("courses.json changed during validation")
    summary = {"configuration": config, "probe": probe, "realGenerations": len(runs), "runs": runs,
               "totals": {key: sum(bool(run.get(key)) for run in runs) for key in
                          ("providerResponse", "jsonParse", "schemaValid", "semanticValid", "solverValid", "qualityGate", "judgeApproved", "published")},
               "providerCalls": len(events), "tokens": {key: sum(e.get("usage", {}).get(key, 0) for e in events) for key in
                          ("prompt_tokens", "completion_tokens", "total_tokens")},
               "coursesRegistryUnchanged": before == after,
               "status": "APPROVED" if any(run.get("published") for run in runs) else "REJECTED"}
    save(args.output / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "probe": probe, "realGenerations": len(runs), "totals": summary["totals"]}, ensure_ascii=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe", "run"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=("groq", "openrouter", "openai", "openai_compatible"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--mode", choices=("strict", "best_effort", "json_mode"), default="strict")
    parser.add_argument("--runs", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--probes", type=int, choices=range(1, 11), default=5)
    parser.add_argument("--difficulty", choices=("normal", "hard"), default="hard")
    parser.add_argument("--reasoning-effort", choices=("none", "minimal", "low", "medium", "high"))
    parser.add_argument("--timeout", type=int, choices=range(30, 601), default=120)
    args = parser.parse_args()
    load_dotenv()
    os.environ["STUDIO_AI_TIMEOUT"] = str(args.timeout)
    result = asyncio.run(validate_runs(args))
    if result["probe"]["status"] != "pass" or (args.command == "run" and result["status"] != "APPROVED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
