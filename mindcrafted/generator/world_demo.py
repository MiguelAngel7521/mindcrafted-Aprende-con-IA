"""Authored regression fixtures. Never presented as an AI-approved campaign."""

SOURCE = """En una red los paquetes deben alcanzar su destino; un enlace sin salida no entrega información.
Cada router puede procesar dos paquetes a la vez. Distribuir la carga entre dos routers evita congestión.
Primero se identifica el destino antes de encapsular el mensaje. Se encapsula el mensaje antes de seleccionar una ruta.
Se selecciona una ruta antes de entregar el paquete.
La memoria RAM guarda datos temporales. El disco conserva datos persistentes. La CPU ejecuta instrucciones.
"""


def rule(rid, skill, description, evidence):
    return {"id": rid, "skill": skill, "description": description, "evidence": evidence}


def demo_blueprint(archetypes=("route_network",)):
    puzzles = []
    for kind in archetypes:
        if kind == "route_network":
            puzzles.append({
                "id": "routing", "title": "Ciudad de los Nodos",
                "objective": "Reconecta cuatro emisores sin saturar los dos routers.",
                "introduction": "Cuatro distritos envían un paquete cada uno. B y C admiten dos por turno. X es una vía sin salida. Reconfigura los emisores y envía la carga desde la consola.",
                "reflection": "Evitaste que todos compitieran por el mismo camino. Ahora los cuatro paquetes llegan y la compuerta recibe energía.",
                "hint": "Distribuye dos emisores hacia B y dos hacia C. Los dos routers ya tienen una conexión con D; actívala también.",
                "knowledge": {"concept": "Routing y congestión", "learning_action": "Distribuir físicamente rutas para entregar paquetes respetando la capacidad de los routers.",
                    "requiredRules": [rule("capacity", "network.load_balance", "Respetar capacidad y balancear carga", "Cada router puede procesar dos paquetes a la vez."),
                                      rule("delivery", "network.routing", "Mantener un camino al destino", "En una red los paquetes deben alcanzar su destino; un enlace sin salida no entrega información.")]},
                "mechanics": {"archetype": kind,
                    "nodes": [{"id": n, "label": ("Emisor " if n in "AEFG" else "Router " if n in "BC" else "Destino " if n == "D" else "Vía sin salida ") + n,
                               "capacity": 2 if n in "BC" else 4, "ruleId": "capacity"} for n in ["A", "E", "F", "G", "B", "C", "D", "X"]],
                    "edges": [{"source": n, "target": t} for n in "AEFG" for t in ["B", "C", "X"]] + [{"source": n, "target": "D"} for n in "BC"],
                    "packets": [{"id": "packet_" + n, "source": n, "target": "D", "amount": 1, "ruleId": "delivery"} for n in "AEFG"]}})
        elif kind == "switch_sequence":
            puzzles.append({
                "id": "sequence", "title": "La cadena del mensaje", "objective": "Energiza las etapas del envío en un orden válido.",
                "introduction": "La máquina solo transmite si sus etapas reciben energía en el orden correcto. Lee las reglas del proceso y activa los interruptores caminando entre ellos.",
                "reflection": "El mensaje tiene destino, envoltura y camino. La cadena vuelve a transmitir.",
                "hint": "Identifica el destino, encapsula, enruta y entrega. R reinicia toda la cadena si cambias de idea.",
                "knowledge": {"concept": "Dependencias del envío de datos", "learning_action": "Activar etapas físicas respetando las dependencias del proceso de transmisión.",
                    "requiredRules": [rule("address_first", "network.addressing", "Identificar antes de encapsular", "Primero se identifica el destino antes de encapsular el mensaje."),
                                      rule("encapsulate_first", "network.encapsulation", "Encapsular antes de enrutar", "Se encapsula el mensaje antes de seleccionar una ruta."),
                                      rule("route_first", "network.routing", "Enrutar antes de entregar", "Se selecciona una ruta antes de entregar el paquete.")]},
                "mechanics": {"archetype": kind,
                    "switches": [{"id": n, "label": label} for n, label in [("deliver", "Entregar"), ("address", "Identificar destino"), ("route", "Enrutar"), ("wrap", "Encapsular")]],
                    "constraints": [{"before": a, "after": b, "ruleId": r} for a, b, r in [("address", "wrap", "address_first"), ("wrap", "route", "encapsulate_first"), ("route", "deliver", "route_first")]]}})
        elif kind == "push_blocks":
            puzzles.append({
                "id": "hardware", "title": "El taller de la memoria", "objective": "Lleva los módulos a los equipos que necesitan su función.",
                "introduction": "Empuja RAM, DISCO y CPU hacia sus puestos. Hay un puesto que no necesita ninguno. Puedes rodear los módulos y reiniciar con R sin perder las otras misiones.",
                "reflection": "Cada equipo recibe la función que necesita: datos temporales, persistencia y ejecución.",
                "hint": "RAM sirve a datos temporales; DISCO a persistencia; CPU a instrucciones. Empuja desde el lado opuesto al destino.",
                "knowledge": {"concept": "Funciones del hardware", "learning_action": "Transportar módulos físicos al equipo cuya necesidad coincide con su función.",
                    "requiredRules": [rule("ram_rule", "hardware.ram", "Asignar memoria temporal", "La memoria RAM guarda datos temporales."),
                                      rule("disk_rule", "hardware.disk", "Asignar almacenamiento persistente", "El disco conserva datos persistentes."),
                                      rule("cpu_rule", "hardware.cpu", "Asignar ejecución", "La CPU ejecuta instrucciones.")]},
                "mechanics": {"archetype": kind, "board": ["########", "#......#", "#......#", ".......#", "#......#", "#......#", "########"],
                    "spawn": {"x": 1, "y": 3},
                    "blocks": [{"id": n, "kind": n, "x": 2, "y": y, "ruleId": r} for n, y, r in [("RAM", 2, "ram_rule"), ("DISCO", 3, "disk_rule"), ("CPU", 4, "cpu_rule")]],
                    "goals": [{"id": "goal_" + n, "label": label, "accepts": [n], "x": 4, "y": y, "ruleId": r} for n, y, r, label in
                              [("RAM", 2, "ram_rule", "Datos temporales"), ("DISCO", 3, "disk_rule", "Persistencia"), ("CPU", 4, "cpu_rule", "Instrucciones"), ("RED", 5, "cpu_rule", "Comunicaciones")]]}})
        else:
            raise ValueError(kind)
    return {"title": "Ciudad de los Nodos", "introduction": "La ciudad perdió sus conexiones. Camina, conversa y devuelve la energía a sus distritos.", "puzzles": puzzles}


def boss_blueprint():
    """Transfer capacity and delivery to a five-emitter, three-router relay."""
    blueprint = demo_blueprint()
    puzzle = blueprint["puzzles"][0]
    puzzle.update(id="relay_boss", role="boss", title="El relé central",
                  objective="Devuelve la energía al relé: entrega cinco paquetes usando tres routers limitados.",
                  introduction="El relé central conecta cinco distritos. Cada router admite dos paquetes. Aquí tendrás que combinar lo aprendido sobre capacidad y caminos completos.",
                  reflection="Los cinco paquetes llegaron: combinaste rutas conectadas con reparto de carga. El relé central vuelve a iluminar la ciudad.",
                  hint="Dos routers pueden cargar dos paquetes cada uno; el tercero recibirá el restante. Comprueba también las salidas hacia D.")
    m = puzzle["mechanics"]
    m["nodes"] = [{"id": n, "label": ("Emisor " if n in "AEFGH" else "Router " if n in "BCJ" else "Destino " if n == "D" else "Vía sin salida ") + n,
                   "capacity": 2 if n in "BCJ" else 5, "ruleId": "capacity"} for n in "AEFGHBCJDX"]
    m["edges"] = [{"source": n, "target": t} for n in "AEFGH" for t in "BCJX"] + [{"source": n, "target": "D"} for n in "BCJ"]
    m["packets"] = [{"id": "packet_" + n, "source": n, "target": "D", "amount": 1, "ruleId": "delivery"} for n in "AEFGH"]
    blueprint["title"] = puzzle["title"]
    return blueprint
