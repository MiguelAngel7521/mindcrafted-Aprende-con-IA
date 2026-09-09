"""Contenido y respuestas de IA controladas; nunca se usan en producción."""
from copy import deepcopy

TECH_SOURCE = 'Una variable almacena un valor que se actualiza mediante asignaciones. Un algoritmo puede sumar, restar o multiplicar ese valor y seguir sus estados paso a paso. En esta red didáctica los nodos representan dispositivos y las conexiones dirigidas permiten enviar paquetes únicamente en el sentido indicado por las flechas. Un router conecta dispositivos, un paquete transporta datos y un servidor responde solicitudes.'


def technology_fixture():
    plan=fixture('laboratory')
    plan.update(subject='Tecnología',world='technology')
    specs=[('packet_route','Reconecta la red',dict(nodes=['Emisor','Router','Servidor'],edges=[[0,1],[1,2]],start=0,target=2)),
           ('algorithm_trace','Sigue la variable',dict(initial=2,operations=[dict(op='add',value=3),dict(op='multiply',value=2),dict(op='subtract',value=1)])),
           ('concept_links','Servicios conectados',dict(pairs=[dict(left='Router',right='Conecta dispositivos'),dict(left='Paquete',right='Transporta datos'),dict(left='Servidor',right='Responde solicitudes')]))]
    for p,(kind,title,data) in zip(plan['puzzles'],specs):
        p.update(kind=kind,title=title,concept=title,data=data,evidence=TECH_SOURCE,explanation=TECH_SOURCE,instruction='Aplica las reglas del material para restaurar la conexión y completar la misión.')
    return plan

SOURCES = {
    "mathematics": "Una ecuación conserva la igualdad al aplicar la misma operación en ambos miembros. Para resolver 2x + 4 = 14, resta cuatro a ambos lados y divide entre dos. Una fracción representa partes iguales de un todo: el numerador cuenta las partes elegidas y el denominador indica el total de partes iguales. Tres cuartos significa elegir tres de cuatro partes iguales.",
    "laboratory": "La ley de Ohm establece que I = V / R en un circuito ideal de corriente continua. La corriente se mide en amperios, el voltaje en voltios y la resistencia eléctrica en ohmios. Con una resistencia total de seis ohmios y doce voltios, la corriente es de dos amperios. Un interruptor abierto interrumpe el circuito y la corriente es cero.",
    "biology": "La germinación comienza cuando la semilla absorbe agua. Después emerge la raíz y finalmente aparece el brote. La raíz absorbe agua y minerales, las hojas realizan la fotosíntesis y el tallo sostiene la planta. Sin agua la semilla no puede iniciar este proceso. Las plantas necesitan luz para realizar la fotosíntesis.",
}

def fixture(world="mathematics"):
    def puzzle(kind, title, data, evidence, instruction):
        return dict(kind=kind, title=title, concept=title, instruction=instruction,
                    evidence=evidence, hint="Consulta la regla descrita en el fragmento de tus apuntes.",
                    explanation=evidence, data=data)
    if world == "mathematics":
        puzzles = [
            puzzle("balance_equation", "Despeja la incógnita", {"a":2,"b":4,"c":14}, SOURCES[world].split('. ')[0]+'.', "Conserva la igualdad hasta dejar sola la incógnita."),
            puzzle("fraction_fill", "Representa tres cuartos", {"numerator":3,"denominator":4}, "Tres cuartos significa elegir tres de cuatro partes iguales.", "Selecciona tres cuartos de las partes iguales del panel."),
            puzzle("evidence_choice", "Miembros de la igualdad", {"options":["Restar cuatro en ambos miembros", "Restar cuatro solo a la izquierda", "Sumar cuatro solo a la derecha"],"answer":0}, "Para resolver 2x + 4 = 14, resta cuatro a ambos lados y divide entre dos.", "¿Qué operación permite comenzar a despejar 2x + 4 = 14?"),
        ]
    elif world == "laboratory":
        puzzles = [
            puzzle("circuit_target", "Ajusta la corriente", {"resistance":6,"target_voltage":12}, SOURCES[world].split('. ')[0]+'.', "Ajusta la batería para alcanzar dos amperios en el circuito."),
            puzzle("concept_links", "Magnitudes eléctricas", {"pairs":[{"left":"Corriente","right":"Amperios"},{"left":"Voltaje","right":"Voltios"},{"left":"Resistencia","right":"Ohmios"}]}, "La corriente se mide en amperios, el voltaje en voltios y la resistencia eléctrica en ohmios.", "Relaciona cada magnitud eléctrica con su unidad de medida."),
            puzzle("evidence_choice", "Circuito abierto", {"options":["Cero amperios", "Dos amperios", "Doce amperios"],"answer":0}, "Un interruptor abierto interrumpe el circuito y la corriente es cero.", "¿Qué corriente circula después de abrir el interruptor?"),
        ]
    else:
        puzzles = [
            puzzle("process_order", "La semilla despierta", {"steps":["La semilla absorbe agua", "Emerge la raíz", "Aparece el brote"]}, "La germinación comienza cuando la semilla absorbe agua. Después emerge la raíz y finalmente aparece el brote.", "Ordena los acontecimientos de la germinación de una semilla."),
            puzzle("concept_links", "Órganos de la planta", {"pairs":[{"left":"Raíz","right":"Absorbe agua y minerales"},{"left":"Hojas","right":"Realizan la fotosíntesis"},{"left":"Tallo","right":"Sostiene la planta"}]}, "La raíz absorbe agua y minerales, las hojas realizan la fotosíntesis y el tallo sostiene la planta.", "Conecta los órganos de la planta con sus funciones."),
            puzzle("evidence_choice", "Una semilla seca", {"options":["No puede iniciar la germinación", "Germina sin agua", "Ya tiene un brote"],"answer":0}, "Sin agua la semilla no puede iniciar este proceso.", "Una semilla no recibe agua. ¿Qué ocurre con su germinación?"),
        ]
    return deepcopy(dict(subject={"mathematics":"Matemáticas","laboratory":"Física","biology":"Biología"}[world], world=world,
                         introduction="Resuelve retos aplicando los conceptos y ejemplos de tus apuntes.", puzzles=puzzles))
