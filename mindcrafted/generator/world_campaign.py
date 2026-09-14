"""Compose approved lessons into a portable campaign using one persistent canvas."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

from .world import schema_check, unique, validate_world, world_hash
from .world_knowledge import validate_knowledge_graph
from .world_package import CHECKS, browser_probe, check_judge, render_html
from .world_schema import CAMPAIGN_SCHEMA


def campaign_hash(campaign):
    return hashlib.sha256(json.dumps(campaign, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def assemble_campaign(packages, course_id="local_campaign", title=None, *, development=False):
    if not isinstance(packages, list) or not 1 <= len(packages) <= 24:
        raise ValueError("Una campaña necesita entre 1 y 24 regiones")
    regions, knowledge, quality = [], [], []
    taught = set()
    for index, package in enumerate(packages):
        config, world = package.get("config", {}), package.get("world")
        if config.get("generationMode") != "world" or not isinstance(world, dict):
            raise ValueError("La campaña solo admite regiones World V2")
        digest = world_hash(world)
        if not set(world.get("priorSkills", [])).issubset(taught):
            raise ValueError("Las habilidades previas no fueron enseñadas en la campaña")
        taught.update(r["skill"] for p in world["puzzles"] for r in p["knowledge"]["requiredRules"])
        if config.get("worldHash") != digest:
            raise ValueError("El mundo cambió después de generarse")
        graph = package.get("knowledgeGraph")
        validate_knowledge_graph(graph)
        if graph["worldHash"] != digest or graph["source"]["sha256"] != config.get("sourceHash"):
            raise ValueError("El grafo de conocimiento no corresponde a la región")
        report = package.get("quality", {})
        if not development and not (report.get("approved") is True and report.get("worldHash") == digest
                and not report.get("errors") and all(report.get("checks", {}).get(k) is True for k in CHECKS)
                and check_judge(report.get("judge"))):
            raise ValueError("Cada región necesita aprobación del QualityGate")
        if development and package.get("developmentDemo") is not True:
            raise ValueError("Solo demos explícitas pueden omitir el juez en desarrollo")
        regions.append({"id": config.get("chunkId") or f"region_{index + 1}", "worldHash": digest,
                        "sourceHash": config["sourceHash"], "world": deepcopy(world)})
        knowledge.append(deepcopy(graph))
        quality.append(deepcopy(report))
    campaign = {"format": "mindcrafted-campaign", "version": 2, "id": course_id,
                "title": title or packages[0]["title"], "regions": regions}
    schema_check(campaign, CAMPAIGN_SCHEMA)
    unique(regions, "regiones de campaña")
    result = deepcopy(packages[0])
    result.update(title=campaign["title"], campaign=campaign, regionKnowledge=knowledge, regionQuality=quality,
                  developmentDemo=development)
    result["config"].update(courseId=course_id, chunkId="campaign", worldHash=campaign_hash(campaign))
    result["config"].pop("nextGameUrl", None)
    return result


def write_campaign(package, output_dir, *, screenshot=None):
    """All gameplay data commit together in game.pkg.json; HTML is a portable export."""
    campaign = package["campaign"]
    schema_check(campaign, CAMPAIGN_SCHEMA)
    if package["config"]["worldHash"] != campaign_hash(campaign):
        raise ValueError("La campaña cambió antes de publicarse")
    if len(package["regionKnowledge"]) != len(campaign["regions"]) or len(package["regionQuality"]) != len(campaign["regions"]):
        raise ValueError("Falta evidencia de validación para alguna región")
    # Recheck the same publication boundary even for callers not using assemble_campaign.
    assemble_campaign([{"world": r["world"], "title": r["world"]["title"],
                        "config": {"generationMode": "world", "chunkId": r["id"], "worldHash": r["worldHash"], "sourceHash": r["sourceHash"]},
                        "knowledgeGraph": package["regionKnowledge"][i], "quality": package["regionQuality"][i],
                        "developmentDemo": package.get("developmentDemo", False)} for i, r in enumerate(campaign["regions"])],
                      campaign["id"], campaign["title"], development=package.get("developmentDemo", False))
    trace = []
    for index, region in enumerate(campaign["regions"]):
        if index:
            trace.append({"type": "region", "index": index})
        # Source membership was checked in the individual publication gate. Here
        # the preserved literal evidence lets us verify spatial/runtime composition.
        source = "\n".join(e["quote"] for e in package["regionKnowledge"][index]["evidence"])
        report = validate_world(region["world"], source)
        if not report["ok"]:
            raise ValueError("Región inválida al componer: " + "; ".join(report["errors"]))
        trace.extend(report["walkthrough"])
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    package = deepcopy(package)
    package["campaignChecks"] = browser_probe(package, trace, screenshot=screenshot)
    manifest = {"format": "mindcrafted-campaign", "version": 2, "id": campaign["id"],
                "title": campaign["title"], "hash": package["config"]["worldHash"],
                "regions": [{"id": r["id"], "title": r["world"]["title"], "worldHash": r["worldHash"],
                             "puzzles": len(r["world"]["puzzles"])} for r in campaign["regions"]],
                "developmentDemo": package.get("developmentDemo", False), "checks": package["campaignChecks"]}
    # Compute every payload before committing the authoritative package last.
    files = {"campaign.json": json.dumps(manifest, ensure_ascii=False, indent=2),
             "knowledge.json": json.dumps(package["regionKnowledge"], ensure_ascii=False, indent=2),
             "index.html": render_html(package), "game.pkg.json": json.dumps(package, ensure_ascii=False, indent=2)}
    for name, data in files.items():
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=out, delete=False, prefix=".campaign-") as handle:
            handle.write(data)
            temporary = Path(handle.name)
        temporary.replace(out / name)
    return manifest
