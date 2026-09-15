"""Offline development utilities: no API key, no fabricated AI approval."""

import argparse
import json
from pathlib import Path

from .world import compile_world
from .world_demo import SOURCE, boss_blueprint, demo_blueprint
from .world_package import make_package, quality_gate, render_html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "check"])
    parser.add_argument("--output", type=Path, default=Path("output/world-demo"))
    parser.add_argument("--campaign", action="store_true", help="Recorrido continuo de tres regiones con boss de transferencia")
    parser.add_argument("--archetype", choices=["machine_configuration", "resource_balance", "node_connect", "route_network", "switch_sequence", "push_blocks"], help="Validar o exportar un único arquetipo")
    parser.add_argument("--pillars", action="store_true", help="Demo integrada de node_connect, resource_balance y machine_configuration")
    args = parser.parse_args()
    if sum((bool(args.archetype), args.campaign, args.pillars)) > 1:
        parser.error("--archetype, --campaign y --pillars son alternativas")
    if args.campaign:
        from .world_campaign import assemble_campaign, write_campaign
        packages = []
        for index, blueprint in enumerate([demo_blueprint(("route_network", "switch_sequence")), demo_blueprint(("push_blocks",)), boss_blueprint()]):
            world = compile_world(blueprint, SOURCE, difficulty="hard" if index == 2 else "normal",
                                  prior_skills=("network.load_balance", "network.routing") if index == 2 else ())
            package = make_package(world, SOURCE, f"region_{index + 1}")
            package["developmentDemo"] = True
            packages.append(package)
        campaign = assemble_campaign(packages, "demo_campaign", "Ciudad de los Nodos", development=True)
        manifest = write_campaign(campaign, args.output, screenshot=args.output / "world.png" if args.command == "check" else None)
        print(json.dumps({"developmentDemo": True, "regions": len(manifest["regions"]), "judge": "not_run", "html": str(args.output / "index.html")}, ensure_ascii=False))
        return
    if args.pillars:
        from .pillar_demo import SOURCE as source, blueprint
        design = blueprint()
    elif args.archetype == "machine_configuration":
        from .machine_configuration_demo import SOURCE as source, blueprint
        design = blueprint()
    elif args.archetype == "resource_balance":
        from .resource_balance_demo import SOURCE as source, blueprint
        design = blueprint()
    elif args.archetype == "node_connect":
        from .node_connect_demo import SOURCE as source, blueprint
        design = blueprint()
    else:
        source = SOURCE
        design = demo_blueprint((args.archetype,) if args.archetype else ("route_network", "switch_sequence", "push_blocks"))
    world = compile_world(design, source, difficulty="hard" if args.pillars or args.archetype in ("node_connect", "resource_balance", "machine_configuration") else "normal")
    package = make_package(world, source, "demo")
    package["developmentDemo"] = True
    package["subtitle"] = "Demo prehecha de desarrollo; sin aprobación de juez IA"
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "check":
        report = quality_gate(world, source, screenshot=args.output / "world.png")
        (args.output / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"checks": report["checks"], "errors": report["errors"], "approved": report["approved"], "judge": "not_run"}, ensure_ascii=False))
        if not all(report["checks"].values()):
            raise SystemExit(1)
    # Explicit development export is separate from publication of generated campaigns.
    (args.output / "index.html").write_text(render_html(package), encoding="utf-8")
    (args.output / "world.json").write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Demo de desarrollo: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
