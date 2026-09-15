"""Explicit mixed fixture. This is authored composition, not a mechanic selector."""
from . import node_connect_demo, resource_balance_demo, machine_configuration_demo

SOURCE = '\n'.join(module.SOURCE for module in (node_connect_demo, resource_balance_demo, machine_configuration_demo))


def blueprint():
    return {"title":"El taller de sistemas", "introduction":"Reconstruye las dependencias, reparte las cargas y configura la estación de archivo para recuperar el taller.",
            "puzzles":[module.blueprint()['puzzles'][0] for module in (node_connect_demo, resource_balance_demo, machine_configuration_demo)]}
