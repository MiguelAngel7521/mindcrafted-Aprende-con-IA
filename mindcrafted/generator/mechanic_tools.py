"""Offline selector evidence for a UTF-8 source. No model calls or publication."""
import argparse
import json
from pathlib import Path

from .knowledge_features import LearningObjective, build_structure_graph
from .mechanic_selector import MechanicSelector, PROFILE_BY_ID


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--objective', required=True)
    parser.add_argument('--objective-id', default='material')
    parser.add_argument('--intent', choices=['explore','connect','distribute','configure'], default='explore')
    parser.add_argument('--relation', action='append', help='Scope to explicit relation IDs; repeat as needed')
    parser.add_argument('--mode', choices=['AUTO', *PROFILE_BY_ID], default='AUTO')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.source.stat().st_size > 240000:
        parser.error('SOURCE_BOUNDS_ERROR: UTF-8 input exceeds 240000 bytes')
    source = args.source.read_text(encoding='utf-8')
    graph = build_structure_graph(source)
    objective = LearningObjective(args.objective_id, args.objective,
                                  relation_ids=tuple(args.relation) if args.relation is not None else None,
                                  intent=args.intent)
    result = MechanicSelector().select(graph, source, objective, mode=args.mode)
    result['sourceLength'] = len(source)
    # The portable report includes IDs/counts/hash, not the student's source text.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'selectedMechanic': result['selectedMechanic'],
                      'output': str(args.output)}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    main()
