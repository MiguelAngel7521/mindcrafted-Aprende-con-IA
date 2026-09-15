"""Authored layered-software fixture; never an AI-approved publication by itself."""

SOURCE = """En esta arquitectura por capas, la presentación depende únicamente de servicios.
Los servicios dependen de repositorios y los repositorios del almacenamiento.
La interfaz utiliza una sola entrada de servicio para mantener una dependencia explícita.
Para consultar datos debe existir una cadena dirigida desde la presentación hasta el almacenamiento.
Dos servicios equivalentes permiten elegir una implementación sin saltarse las capas.
"""


def blueprint():
    return {"title": "El archivo desconectado", "introduction": "Las dependencias del archivo están rotas. Reconstruye sus componentes para abrir el acceso.",
            "puzzles": [{
                "id": "layers", "title": "Reconstruir las dependencias",
                "objective": "Conecta la presentación con el almacenamiento respetando las capas y una sola entrada de servicio.",
                "introduction": "El archivo quedó aislado. Cada componente indica su función. E selecciona un origen; camina al destino y pulsa E para conectar. Repetir ese par lo desconecta. La consola comprueba tu diseño; R limpia los enlaces.",
                "reflection": "Respetaste las capas y construiste un camino completo con una sola entrada. La máquina vuelve a funcionar y la compuerta del archivo está abierta.",
                "hint": "Elige Portal → Servicio A → Repositorio → Archivo. Servicio B también puede sustituir a Servicio A. No conectes el Portal directamente con el Archivo.",
                "knowledge": {
                    "concept": "Dependencias en una arquitectura de software por capas",
                    "learning_action": "Construir enlaces dirigidos entre componentes físicos según sus responsabilidades y verificar una cadena de dependencias completa.",
                    "requiredRules": [
                        {"id": "layering", "skill": "software.layers", "description": "Presentación → servicio → repositorio → almacenamiento; no se saltan capas.",
                         "evidence": "En esta arquitectura por capas, la presentación depende únicamente de servicios.\nLos servicios dependen de repositorios y los repositorios del almacenamiento."},
                        {"id": "single_entry", "skill": "software.dependencies", "description": "El Portal tiene exactamente una conexión saliente de servicio.",
                         "evidence": "La interfaz utiliza una sola entrada de servicio para mantener una dependencia explícita."},
                        {"id": "availability", "skill": "software.reachability", "description": "Existe una cadena dirigida desde Portal hasta Archivo.",
                         "evidence": "Para consultar datos debe existir una cadena dirigida desde la presentación hasta el almacenamiento."},
                    ]},
                "mechanics": {
                    "archetype": "node_connect", "schemaVersion": 1,
                    "nodes": [{"id": nid, "label": label, "kind": kind} for nid, label, kind in [
                        ("UI", "Portal", "presentacion"), ("API", "Servicio A", "servicio"),
                        ("ALT", "Servicio B", "servicio"), ("REPO", "Repositorio", "repositorio"), ("DB", "Archivo", "almacenamiento")]],
                    "edges": [{"id": source + "_" + target, "source": source, "target": target} for source, target in [
                        ("UI", "API"), ("UI", "ALT"), ("API", "REPO"), ("ALT", "REPO"), ("REPO", "DB"),
                        ("UI", "REPO"), ("UI", "DB"), ("API", "DB"), ("ALT", "DB"), ("DB", "REPO"), ("REPO", "API")]],
                    "connectionRules": [
                        {"kind": "compatible", "allowed": [{"sourceKind": source, "targetKind": target} for source, target in [
                            ("presentacion", "servicio"), ("servicio", "repositorio"), ("repositorio", "almacenamiento")]], "ruleId": "layering"},
                        {"kind": "degree", "node": "UI", "direction": "out", "min": 1, "max": 1, "ruleId": "single_entry"}],
                    "goals": [{"source": "UI", "target": "DB", "ruleId": "availability"}],
                }}]}
