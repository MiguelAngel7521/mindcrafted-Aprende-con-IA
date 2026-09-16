"""Source graph → independent objectives → selected authored fixtures.

The selector chooses; this small offline demonstration looks up an existing
fixture only after selection. It does not generate academic facts or plan a course.
"""
from . import node_connect_demo, resource_balance_demo, machine_configuration_demo
from .knowledge_features import build_structure_graph, objective_from_evidence
from .mechanic_selector import MechanicSelector

MODULES = (node_connect_demo, resource_balance_demo, machine_configuration_demo)
SOURCE = '\n'.join(m.SOURCE for m in MODULES)


def selected_blueprint():
    graph = build_structure_graph(SOURCE)
    catalog = {m.blueprint()['puzzles'][0]['mechanics']['archetype']: m.blueprint()['puzzles'][0] for m in MODULES}
    objectives = [objective_from_evidence(graph, p['objective'], [r['evidence'] for r in p['knowledge']['requiredRules']],
                                          objective_id=p['id']) for p in catalog.values()]
    results, puzzles, history = [], [], []
    for objective in objectives:
        selection = MechanicSelector().select(graph, SOURCE, objective, history=history)
        if selection['status'] != 'SELECTED':
            raise ValueError(selection['status'])
        selected = selection['selectedMechanic']
        puzzles.append(catalog[selected])
        results.append(selection)
        history.append(selected)
    return {'title': 'El taller de sistemas',
            'introduction': 'Reconstruye conexiones, distribuye recursos y configura la estación para recuperar el taller.',
            'puzzles': puzzles}, {'graph': graph, 'selections': results}
