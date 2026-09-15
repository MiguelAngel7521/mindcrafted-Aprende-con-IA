"""An explicit educational system model, not universal hardware specifications."""
SOURCE = """El archivo usa una máquina configurable con componentes de almacenamiento, enlace, caché y memoria.
El modo operativo requiere un componente de almacenamiento persistente para conservar datos al apagarse.
En esta máquina el componente de enlace diferido y el modo de caché diferida son incompatibles: ambos aplazan confirmar escrituras.
El parámetro memoria debe reservar entre cuatro y ocho unidades para procesar el archivo.
La configuración total no puede superar ocho unidades: suma la reserva de memoria y los búferes de caché.
El modo de caché requiere estar activo para procesar el archivo: puede ser diferido o inmediato.
El sistema debe tener un componente de enlace instalado para entregar el archivo.
El objetivo requiere que el parámetro de modo esté operativo; mantenimiento y diagnóstico no procesan archivos.
La memoria permite dos, cuatro u ocho unidades. Caché apagada reserva cero, diferida tres e inmediata una unidad adicional.
El almacenamiento puede ser volátil o persistente. El enlace puede ser diferido o confirmado.
El enlace diferido permite continuar sin esperar confirmación, pero necesita caché inmediata en este escenario.
"""


def blueprint():
    lines = SOURCE.splitlines()
    def condition(control, *values):
        return {"control": control, "values": list(values)}
    rules = [
        {"kind":"dependency", "ruleId":"durability", "when":condition("mode", "online"), "then":condition("storage", "durable")},
        {"kind":"exclusion", "ruleId":"confirmation", "left":condition("link", "deferred"), "right":condition("cache", "writeback")},
        {"kind":"range", "ruleId":"working_memory", "control":"memory", "min":4, "max":8},
        {"kind":"capacity", "ruleId":"budget", "unit":"unidades de memoria", "max":8, "terms":[
            {"control":"memory", "costs":[{"value":v,"amount":n} for v,n in [("small",2),("medium",4),("large",8)]]},
            {"control":"cache", "costs":[{"value":v,"amount":n} for v,n in [("off",0),("writeback",3),("writethrough",1)]]}]},
        {"kind":"required", "ruleId":"caching", "condition":condition("cache", "writeback", "writethrough")},
    ]
    return {"title":"El archivo detenido", "introduction":"Configura la máquina para reactivar el transporte del archivo.", "puzzles":[{
        "id":"machine", "title":"Reactivar la estación de archivo",
        "objective":"Instala componentes y ajusta el sistema para procesar el archivo sin perder datos ni exceder memoria.",
        "introduction":"La estación está detenida. Cada ranura y selector está en el suelo del taller: E cambia su componente o parámetro. Un ciclo de ranura permite retirarlo. Observa los indicadores y el presupuesto compartido. Activa en la consola; puedes corregir cualquier configuración o reiniciar con R.",
        "reflection":"Configuraste el almacenamiento, la confirmación y los búferes dentro del presupuesto. La estación procesa el archivo; el transporte y la compuerta vuelven a funcionar.",
        "hint":"Instala Persistente y enlace Diferido, pon modo Operativo, caché Inmediata y memoria de cuatro unidades. También funciona enlace Confirmado con caché Diferida o Inmediata.",
        "knowledge":{"concept":"Configuración consistente de almacenamiento y memoria",
            "learning_action":"Instalar componentes y ajustar confirmación, caché y memoria según dependencias y recursos para activar un servicio persistente.",
            "requiredRules":[{"id":rid,"skill":"configuration."+rid,"description":description,"evidence":"\n".join(lines[4:10]) if rid == "budget" else lines[i]} for rid,description,i in [
                ("durability","Operativo requiere almacenamiento persistente.",1),
                ("confirmation","Enlace diferido y caché diferida no pueden coexistir.",2),
                ("working_memory","La reserva de memoria está entre 4 y 8 unidades.",3),
                ("budget","Reserva de memoria + búferes de caché ≤ 8 unidades.",4),
                ("caching","La caché debe estar activa, diferida o inmediata.",5),
                ("delivery","Instala un componente de enlace para entregar el archivo.",6),
                ("operation","Selecciona modo operativo para procesar el archivo.",7)]]},
        "mechanics":{"archetype":"machine_configuration","schemaVersion":1,
            "machine":{"id":"archive_station","label":"Estación de archivo"},
            "components":[{"id":id,"label":label} for id,label in [("volatile","Volátil"),("durable","Persistente"),("deferred","Diferido"),("confirmed","Confirmado")]],
            "slots":[{"id":"storage","label":"Almacenamiento","components":["volatile","durable"]},
                     {"id":"link","label":"Enlace","components":["deferred","confirmed"]}],
            "parameters":[
                {"id":"mode","label":"Modo","initial":"maintenance","values":[{"id":id,"label":label,"quantity":None} for id,label in [("maintenance","Mantenimiento"),("diagnostic","Diagnóstico"),("online","Operativo")]]},
                {"id":"cache","label":"Caché","initial":"off","values":[{"id":id,"label":label,"quantity":n} for id,label,n in [("off","Apagada",0),("writeback","Diferida",3),("writethrough","Inmediata",1)]]},
                {"id":"memory","label":"Memoria","initial":"small","values":[{"id":id,"label":str(n)+" unidades","quantity":n} for id,n in [("small",2),("medium",4),("large",8)]]}],
            "configurationRules":rules,
            "goals":[{"kind":"required","ruleId":"delivery","condition":condition("link","deferred","confirmed")},
                     {"kind":"required","ruleId":"operation","condition":condition("mode","online")}],
            "tradeoffs":[{"control":"link","preferredValues":["deferred"],"reason":lines[10]}]}}]}
