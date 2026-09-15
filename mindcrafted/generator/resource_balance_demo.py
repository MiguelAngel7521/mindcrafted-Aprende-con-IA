"""Authored resource scheduling fixture grounded in a small, explicit scenario."""
SOURCE = """El sistema reparte cuatro cargas indivisibles entre tres ejecutores.
Las cargas de tiempo real requieren recursos de baja latencia; las cargas por lotes pueden usar cualquier ejecutor.
La carga total asignada a cada ejecutor no debe superar su capacidad de cuatro unidades.
El servicio requiere asignar todas las cargas a un ejecutor para continuar.
Audio y Control consumen tres unidades cada uno; Informe y Copia consumen dos unidades cada uno.
Archivo es un ejecutor por lotes; Rápido y Auxiliar son recursos de baja latencia equivalentes.
"""


def blueprint():
    return {"title": "El taller saturado", "introduction": "Distribuye los procesos para devolver la energía al taller.", "puzzles": [{
        "id": "balance", "title": "Recuperar la capacidad del taller",
        "objective": "Asigna todas las cargas respetando latencia y capacidad; restaura la compuerta.",
        "introduction": "Cada módulo lleva una carga indivisible. E cambia su ejecutor y permite retirarlo al completar el ciclo. Observa los cables y medidores. La consola activa el reparto; R devuelve las cargas al origen.",
        "reflection": "El reparto mantiene los procesos de tiempo real en recursos adecuados sin saturar ejecutores. El taller vuelve a tener energía y se abre la compuerta.",
        "hint": "Reparte Audio y Control entre Rápido y Auxiliar. Coloca Informe y Copia en Archivo. Cada ejecutor queda dentro de cuatro unidades.",
        "knowledge": {"concept": "Asignación de recursos con latencia y capacidad",
            "learning_action": "Distribuir cargas indivisibles según requisitos de latencia y suma de consumo para restaurar un servicio.",
            "requiredRules": [
                {"id": "latency", "skill": "resources.latency", "description": "Tiempo real requiere baja latencia; lotes acepta cualquier ejecutor.", "evidence": SOURCE.splitlines()[1]},
                {"id": "capacity", "skill": "resources.capacity", "description": "Suma de carga por ejecutor ≤ 4 unidades.", "evidence": "\n".join(SOURCE.splitlines()[2:6])},
                {"id": "service", "skill": "resources.availability", "description": "Todas las cargas deben tener un ejecutor.", "evidence": SOURCE.splitlines()[3]}]},
        "mechanics": {"archetype": "resource_balance", "schemaVersion": 1,
            "loads": [{"id": id, "label": label, "kind": kind, "amount": amount} for id, label, kind, amount in [
                ("audio", "Audio", "realtime", 3), ("control", "Control", "realtime", 3),
                ("report", "Informe", "batch", 2), ("copy", "Copia", "batch", 2)]],
            "targets": [{"id": id, "label": label, "kind": kind} for id, label, kind in [
                ("archive", "Archivo", "batch"), ("fast", "Rápido", "low_latency"), ("aux", "Auxiliar", "low_latency")]],
            "allocationRules": [
                {"kind": "compatible", "ruleId": "latency", "allowed": [
                    {"sourceKind": a, "targetKind": b} for a, b in [("realtime", "low_latency"), ("batch", "batch"), ("batch", "low_latency")]]},
                {"kind": "capacity", "ruleId": "capacity", "limits": [{"target": t, "min": 0, "max": 4} for t in ["archive", "fast", "aux"]]}],
            "goals": [{"kind": "all_assigned", "ruleId": "service"}]}}]}
