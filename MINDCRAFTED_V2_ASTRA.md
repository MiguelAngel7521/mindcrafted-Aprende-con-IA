# MINDCRAFTED 2.0 — ARQUITECTURA Y REGLAS PARA ASTRA

## 1. PROPÓSITO DE ESTE DOCUMENTO

Este archivo define la dirección oficial de desarrollo de **MindCrafted 2.0**.

Astra debe leer y respetar este documento antes de:

- modificar arquitectura;
- crear minijuegos;
- crear puzzles;
- modificar el motor del mundo;
- implementar IA;
- crear NPC;
- generar diálogos;
- modificar el sistema de progreso;
- añadir nuevas mecánicas;
- crear tests;
- modificar el pipeline de generación.

Este documento tiene prioridad conceptual sobre implementaciones antiguas del proyecto.

Si existe código viejo que contradice estas reglas, se debe considerar **LEGACY/V1** y no utilizar como referencia para nuevas funcionalidades.

---

# 2. VISIÓN DE MINDCRAFTED

MindCrafted NO debe convertirse en:

> un juego donde el personaje camina hasta un lugar y luego aparece un minijuego separado.

MindCrafted debe convertirse en:

> un RPG educativo donde aprender sea parte de las reglas físicas, lógicas y narrativas del propio mundo.

Inspiraciones conceptuales:

- Undertale: mundo, personajes, dificultad y consecuencias.
- Zelda: puzzles integrados al entorno.
- Portal: aprender reglas mediante experimentación.
- EdGameClaw: generación automática de mecánicas educativas mediante IA.

Sin embargo, MindCrafted NO debe copiar literalmente la arquitectura de EdGameClaw.

MindCrafted debe evolucionar hacia una arquitectura propia:

```text
Material educativo
        ↓
Knowledge Graph
        ↓
Generación de mundo
        ↓
Misiones
        ↓
NPC
        ↓
PuzzleBlueprint
        ↓
Compilador determinista
        ↓
Puzzle físico dentro del mundo
        ↓
Jugador experimenta
        ↓
Jugador aprende
        ↓
El mundo cambia
        ↓
Nueva zona / diálogo / quest / boss
```

---

# 3. REGLA FUNDAMENTAL

## AI DESIGNS — CODE DECIDES

La IA puede diseñar contenido.

El código controla las reglas reales del juego.

La IA NO debe controlar directamente el estado crítico del juego.

### La IA puede generar:

- Knowledge Graph.
- regiones.
- mapas conceptuales.
- quests.
- NPC.
- diálogos.
- pistas.
- narrativa.
- PuzzleBlueprint.
- dificultad.
- distribución de puzzles.
- bosses.
- secuencias educativas.
- consecuencias propuestas.
- ambientación.
- nombres.
- lore.
- objetivos de aprendizaje.

### La IA NO puede ejecutar directamente:

```text
openDoor()
completeQuest()
completePuzzle()
giveXP()
setSolved()
teleportPlayer()
setBKT()
unlockRegion()
modifyInventory()
```

La IA genera una intención declarativa.

El runtime valida y ejecuta.

---

# 4. ARQUITECTURA GENERAL

La arquitectura objetivo es:

```text
                    MATERIAL
                       │
                       ▼
              KNOWLEDGE EXTRACTOR
                       │
                       ▼
                KNOWLEDGE GRAPH
                       │
              ┌────────┴────────┐
              ▼                 ▼
        WORLD PLANNER      QUEST PLANNER
              │                 │
              └────────┬────────┘
                       ▼
                 PUZZLE AGENT
                       │
                       ▼
               PUZZLE BLUEPRINT
                       │
                       ▼
                 JSON SCHEMA
                       │
                       ▼
               PUZZLE COMPILER
                       │
                       ▼
             DETERMINISTIC CORE
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
     VALIDATE        SOLVER         SIMULATE
        │              │               │
        └──────────────┼───────────────┘
                       ▼
                 ANTI-SOFTLOCK
                       │
                       ▼
                  E2E TESTS
                       │
                       ▼
                    AI JUDGE
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
           FAIL                 PASS
             │                   │
             ▼                   ▼
        REPAIR AGENT        WORLD PACKAGE
             │                   │
             └───────────────►   ▼
                            WORLD ENGINE
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
           PLAYER               NPC               PUZZLE
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                         WORLD CONSEQUENCE
                                 │
                                 ▼
                         QUEST / SAVE / BKT
```

---

# 5. WORLD V2 ES LA RUTA PRINCIPAL

World V2 debe convertirse progresivamente en la implementación canónica de MindCrafted.

No crear nuevas funcionalidades importantes exclusivamente sobre sistemas V1.

Los componentes V1 pueden conservarse temporalmente por compatibilidad.

Pero todo sistema nuevo debe diseñarse pensando en World V2.

Astra debe identificar claramente:

```text
V1 / LEGACY
```

y

```text
V2 / CANONICAL
```

No mezclar ambos sistemas innecesariamente.

---

# 6. LOS PUZZLES DEBEN EXISTIR DENTRO DEL MUNDO

Esta es una regla obligatoria.

Un puzzle obligatorio de MindCrafted V2 debe existir físicamente dentro del mismo mundo en el que camina el jugador.

NO crear:

```text
Player
  ↓
Interactúa
  ↓
Overlay
  ↓
Minijuego
  ↓
Cerrar overlay
  ↓
Volver al mundo
```

La arquitectura correcta es:

```text
Player
  ↓
encuentra mecanismo
  ↓
observa mundo
  ↓
interactúa con objetos
  ↓
experimenta
  ↓
resuelve concepto
  ↓
el mundo responde
```

Ejemplos de elementos físicos:

- puertas;
- interruptores;
- terminales;
- routers;
- tuberías;
- cajas;
- plataformas;
- máquinas;
- generadores;
- circuitos;
- NPC;
- puentes;
- nodos;
- recursos;
- servidores;
- cintas transportadoras;
- mecanismos;
- zonas;
- obstáculos.

---

# 7. PROHIBIDO PARA PUZZLES OBLIGATORIOS V2

Un puzzle V2 obligatorio NO debe depender de:

```text
iframe
```

NO debe abrir un segundo juego.

NO debe crear otro canvas independiente.

NO debe depender de:

```text
#mini-game-overlay
```

NO debe sacar al jugador del mundo principal.

NO debe ser simplemente:

```text
Pregunta:
¿Qué significa TCP?

A)
B)
C)
D)
```

Eso puede existir como actividad secundaria opcional, pero NO representa el diseño principal de MindCrafted.

---

# 8. UN SOLO MUNDO

Idealmente:

```text
ONE WORLD
ONE PLAYER
ONE MAIN CANVAS
ONE GAME STATE
```

Los puzzles existen dentro de ese mismo contexto.

Un puzzle puede modificar:

- tiles;
- collision map;
- puertas;
- luces;
- NPC;
- objetos;
- rutas;
- plataformas;
- máquinas;
- región desbloqueada;
- sonido;
- estado ambiental;
- quest actual.

---

# 9. PUZZLEBLUEPRINT

La IA NO debe generar directamente código JavaScript arbitrario para cada puzzle.

La IA debe generar una representación declarativa.

Ejemplo conceptual:

```json
{
  "id": "network_room_01",
  "archetype": "node_connect",
  "runtime": "world",
  "mandatory": true,

  "learning": {
    "concept": "routing",
    "objective": "Comprender cómo encontrar una ruta válida entre nodos."
  },

  "world": {
    "region": "network_lab",
    "anchorEntity": "router_console_01"
  },

  "difficulty": {
    "level": "hard",
    "minSolutionSteps": 7
  },

  "rules": {},

  "success": {
    "setFlags": [
      "network_restored"
    ],
    "openEntity": [
      "server_room_door"
    ]
  },

  "failure": {
    "resettable": true
  }
}
```

Después:

```text
PuzzleBlueprint
      ↓
validate()
      ↓
compile()
      ↓
runtime
```

---

# 10. MECÁNICAS

MindCrafted debe aumentar progresivamente el número de familias de puzzles.

Actualmente pueden existir familias básicas como:

```text
switch_sequence
route_network
push_blocks
```

Pero no debemos depender eternamente de ellas.

Objetivo:

```text
switch_sequence
route_network
push_blocks
node_connect
classification_zones
resource_balance
collect_assemble
spatial_order
timeline_path
machine_configuration
hazard_pattern
npc_deduction
logic_circuit
dependency_graph
flow_control
resource_routing
```

Cada familia debe tener una implementación determinista.

---

# 11. LA IA GENERA INSTANCIAS, NO MOTORES COMPLETOS

Ejemplo:

Crear una vez:

```text
resource_balance
```

Después la IA puede reutilizarla para muchos conceptos.

## Redes

```text
Distribuir tráfico entre routers.
```

## Sistemas Operativos

```text
Distribuir procesos entre CPU/memoria.
```

## Logística

```text
Distribuir paquetes entre vehículos.
```

## Electricidad

```text
Distribuir carga entre circuitos.
```

## Bases de Datos

```text
Distribuir consultas entre servidores.
```

La mecánica interna es segura y determinista.

La IA modifica:

- reglas;
- parámetros;
- mapa;
- contexto;
- restricciones;
- narrativa;
- dificultad;
- cantidad de elementos;
- objetivos;
- pistas;
- consecuencias.

---

# 12. EL CONCEPTO ACADÉMICO DEBE SER NECESARIO

Un puzzle no es educativo simplemente porque muestra palabras académicas.

Debe existir:

```text
LEARNING-MECHANIC COUPLING
```

Pregunta fundamental:

> Si eliminamos el concepto académico, ¿el puzzle se puede resolver prácticamente igual?

Si la respuesta es SÍ:

EL PUZZLE ESTÁ MAL DISEÑADO.

Ejemplo malo:

```text
Mueve tres cajas.

Cuando termines:

¿Qué es una base de datos?
A)
B)
C)
```

El movimiento de cajas no enseña bases de datos.

Ejemplo correcto:

```text
Existen registros.

El jugador debe organizarlos utilizando relaciones.

Una mala relación provoca inconsistencias.

Para abrir la puerta necesita construir correctamente las dependencias.
```

Aquí el conocimiento afecta directamente a la mecánica.

---

# 13. DIFICULTAD

MindCrafted NO debe tratar al estudiante como si el objetivo fuera responder preguntas triviales.

Queremos un juego difícil pero justo.

La dificultad debe surgir de:

- razonamiento;
- planificación;
- observación;
- combinación de conceptos;
- optimización;
- restricciones;
- experimentación;
- deducción;
- administración de recursos.

NO principalmente de:

- memoria literal;
- preguntas ambiguas;
- información escondida injustamente;
- controles malos;
- RNG excesivo.

---

# 14. MODELO DE DIFICULTAD

Cada puzzle debería poder declarar datos como:

```json
{
  "difficulty": {
    "level": "hard",
    "minSolutionSteps": 8,
    "maxRecommendedAttempts": 6,
    "randomSuccessProbabilityMax": 0.1,
    "conceptCount": 2,
    "requiresPlanning": true
  }
}
```

Niveles sugeridos:

```text
INTRO
NORMAL
HARD
EXPERT
BOSS
```

---

# 15. BOSSES

Un boss NO debería ser simplemente:

```text
puzzle normal + más pasos
```

Un boss debe integrar múltiples conceptos aprendidos.

Ejemplo:

```text
BOSS: CENTRO DE DATOS COLAPSADO

FASE 1
Reconectar nodos.

FASE 2
Encontrar rutas correctas.

FASE 3
Balancear recursos.

FASE 4
Resolver congestión.

FASE FINAL
Mantener la red estable bajo presión.
```

Un boss debería utilizar entre:

```text
2 y 4 conceptos previamente aprendidos.
```

Características:

- múltiples fases;
- feedback visual;
- posibilidad de fallar;
- posibilidad de recuperarse;
- estado persistente cuando corresponda;
- pistas graduales;
- solución verificable;
- cambios importantes del mundo.

---

# 16. NPC Y DIÁLOGOS

Los NPC deben formar parte del mundo.

Tipos:

```text
Quest NPC
Tutor NPC
Story NPC
Hint NPC
Challenge NPC
Companion NPC
Boss NPC
```

Los diálogos pueden existir en dos modalidades.

## A. DIÁLOGO GENERADO DURANTE LA CREACIÓN

La IA genera:

```text
dialogues.json
```

Estos diálogos son importantes para:

- narrativa;
- quests;
- tutoriales;
- introducción;
- bosses;
- historia principal.

## B. DIÁLOGO DINÁMICO

NPC opcionales pueden llamar a IA durante gameplay.

Contexto:

```text
NPC
+
WorldState
+
QuestState
+
KnowledgeState
+
Errores recientes
+
Intentos
+
HintLevel
```

Respuesta permitida:

```json
{
  "emotion": "concerned",
  "dialogue": "Hay demasiado tráfico pasando por un solo nodo.",
  "suggestedHintLevel": 2
}
```

El NPC NO controla directamente el mundo.

---

# 17. SISTEMA DE PISTAS

Las pistas deben ser graduales.

## Nivel 0

Ninguna pista.

## Nivel 1

Orientación conceptual.

Ejemplo:

```text
Observa qué nodos reciben más tráfico.
```

## Nivel 2

Orientación estratégica.

```text
Tal vez no conviene que todos los paquetes atraviesen el mismo nodo.
```

## Nivel 3

Ayuda concreta.

```text
Prueba a distribuir la carga entre Router B y Router C.
```

## Nivel 4

Casi solución.

Solo cuando el estudiante ha fallado muchas veces.

La primera interacción NUNCA debe revelar directamente la solución.

---

# 18. AGENT API

La arquitectura debe evolucionar hacia un agente con herramientas controladas.

NO crear un agente completamente libre.

El agente puede disponer de tools como:

```text
analyze_material()
build_knowledge_graph()

design_world()
design_region()
design_quest()

design_puzzle()
design_boss()

compile_world()
compile_puzzle()

validate_world()
validate_puzzle()

solve_puzzle()
simulate_puzzle()

run_quality_gate()
run_e2e_tests()

judge_world()
judge_puzzle()

repair_world()
repair_puzzle()

generate_dialogue()
generate_hint()

package_campaign()
```

---

# 19. CICLO DEL AGENTE

Pipeline objetivo:

```text
GENERATE
   ↓
VALIDATE
   ↓
COMPILE
   ↓
SOLVE
   ↓
SIMULATE
   ↓
TEST
   ↓
AI JUDGE
   ↓

PASS ─────────► PUBLISH

FAIL
  ↓
REPAIR
  ↓
VALIDATE
  ↓
...
```

El agente nunca publica directamente.

---

# 20. QUALITY GATE

Todo contenido generado debe pasar por un QualityGate.

Debe existir una separación clara entre:

```text
DETERMINISTIC QUALITY
```

y

```text
AI QUALITY REVIEW
```

Los tests deterministas tienen prioridad absoluta.

---

# 21. REGLA DE PUBLICACIÓN

Un AI Judge NO puede ignorar un fallo determinista.

Incluso si el Judge devuelve:

```json
{
  "approved": true,
  "score": 100
}
```

si:

```text
solver = FAILED
```

entonces:

```text
PUBLICATION = REJECTED
```

Siempre.

---

# 22. TEST: WORLD NATIVE

Todos los puzzles obligatorios deben:

```text
runtime == "world"
```

Deben tener una entidad física.

Ejemplo:

```text
anchorEntity
```

El anchor debe existir realmente en la región.

---

# 23. TEST: SOLVABILITY

Todo puzzle obligatorio debe poder resolverse.

Debe existir:

```text
solver()
```

o una estrategia equivalente.

Debe demostrar que existe al menos una solución válida.

---

# 24. TEST: ANTI-SOFTLOCK

El jugador NO debe poder destruir permanentemente una partida debido a un error normal.

Debe existir al menos uno:

```text
reset
retry
respawn
alternate path
state recovery
```

Cada puzzle obligatorio debe analizarse buscando softlocks.

---

# 25. TEST: WORLD CONSEQUENCE

Resolver un puzzle debe producir una consecuencia observable.

Ejemplos válidos:

```text
abrir puerta
desbloquear región
mover plataforma
restaurar energía
activar NPC
cambiar diálogo
cambiar iluminación
reparar máquina
crear puente
eliminar obstáculo
iniciar quest
terminar quest
revelar camino
```

Esto NO es suficiente por sí solo:

```text
+100 XP
```

---

# 26. TEST: RANDOM SUCCESS

Hay que evitar puzzles que puedan ganarse apretando cosas aleatoriamente.

Simular múltiples intentos aleatorios:

```text
seed 1
seed 2
seed 3
...
```

Calcular:

```text
randomSuccessRate
```

Un puzzle difícil debería poseer una probabilidad accidental muy baja.

---

# 27. TEST: DIALOGUE ANTI-SPOILER

Los diálogos iniciales NO pueden contener directamente:

- secuencia exacta;
- contraseña;
- solución;
- camino final;
- combinación completa.

Los hints deben respetar sus niveles.

---

# 28. TEST: PERSISTENCE

Probar:

```text
START
  ↓
resolver parcialmente
  ↓
SAVE
  ↓
RELOAD
  ↓
continuar
```

Debe conservarse correctamente:

- player state;
- quest state;
- puzzle state;
- flags;
- inventory;
- unlocked regions;
- BKT;
- NPC state.

No debe duplicarse recompensa.

---

# 29. TEST: E2E

Utilizar Playwright o equivalente.

Comprobar realmente:

```text
load game
↓
player exists
↓
keyboard movement works
↓
collision works
↓
NPC interaction works
↓
puzzle interaction works
↓
solve puzzle
↓
world changes
↓
save
↓
reload
↓
state persists
```

No depender solamente de unit tests.

---

# 30. TEST: LEGACY UI

World V2 debe comprobar:

```text
number_of_main_canvases == 1
```

y:

```text
mini-game-overlay == 0
iframe == 0
```

para contenido obligatorio.

---

# 31. TEST: LEARNING COUPLING

Crear una métrica o evaluación para detectar:

```text
fake educational puzzles
```

Preguntar:

```text
¿Resolver el puzzle requiere comprender el concepto?
```

Si:

```text
NO
```

rechazar o reparar.

---

# 32. TEST: SOURCE GROUNDING

Si el material proviene de:

- PDF;
- DOCX;
- presentación;
- texto;
- apuntes;

los conceptos utilizados deben poder relacionarse con contenido real de la fuente.

La IA NO debe inventar hechos académicos innecesariamente.

Idealmente guardar:

```json
{
  "concept": "routing_table",
  "sourceRefs": [
    "document_1/page_12"
  ]
}
```

---

# 33. TEST DE DIVERSIDAD

Este test es obligatorio para evitar colapso generativo.

Generar múltiples campañas:

```text
20 materiales
×
3 seeds
=
60 mundos
```

Medir:

- archetype usage;
- puzzle similarity;
- layout similarity;
- solution similarity;
- NPC similarity;
- narrative similarity;
- boss similarity.

Ejemplo:

```text
switch_sequence     12%
route_network       18%
push_blocks         10%
node_connect        15%
resource_balance    17%
machine_config      14%
npc_deduction       14%
```

Evitar algo como:

```text
switch_sequence = 82%
```

aunque todos los puzzles sean técnicamente válidos.

---

# 34. REPAIR LOOP

Si un mundo falla:

```text
Candidate 1
   ↓
FAIL
   ↓
Repair

Candidate 2
   ↓
FAIL
   ↓
Repair

Candidate 3
   ↓
FAIL
```

NO publicar automáticamente algo roto.

Después del límite de intentos:

```text
REJECT GENERATION
```

o utilizar únicamente:

```text
PREVIOUSLY APPROVED PACKAGE
```

para exactamente el mismo material/contexto compatible.

---

# 35. IA RECOMENDADA

Arquitectura recomendada:

## PUZZLE / WORLD DESIGNER

```text
Groq
+
openai/gpt-oss-120b
```

Responsabilidades:

- Knowledge Graph.
- World Blueprint.
- Puzzle Blueprint.
- bosses.
- repair.
- AI Judge.

---

## DIÁLOGOS

Modelo rápido:

```text
Groq
+
Qwen
```

Utilizar para:

- NPC;
- hints;
- variaciones narrativas;
- conversaciones opcionales.

---

## FALLBACK

Puede existir:

```text
OpenRouter Free
```

como fallback de desarrollo.

No depender del router aleatorio para tests de reproducibilidad cuando se necesite comparar calidad.

---

# 36. STRUCTURED OUTPUT

Cuando el proveedor lo permita, NO depender solamente de:

```text
"Devuélveme JSON"
```

Utilizar:

```text
JSON Schema
Structured Outputs
Tool Calling
```

El schema debe validar:

- tipos;
- enums;
- campos obligatorios;
- límites;
- relaciones;
- IDs.

---

# 37. SEGURIDAD DEL RUNTIME

No ejecutar código arbitrario producido por IA mediante:

```text
eval()
exec()
new Function()
dynamic script injection
```

No permitir HTML/JS arbitrario de puzzles generado directamente por IA dentro del cliente.

La IA genera datos.

El motor interpreta datos.

```text
AI
 ↓
JSON
 ↓
VALIDATION
 ↓
COMPILER
 ↓
SAFE RUNTIME
```

---

# 38. COMPILADORES POR ARCHETYPE

Arquitectura sugerida:

```text
puzzles/
│
├── base/
│   ├── puzzle_base.py
│   ├── validator.py
│   └── solver.py
│
├── switch_sequence/
│   ├── schema.py
│   ├── compiler.py
│   ├── solver.py
│   └── tests/
│
├── route_network/
│
├── push_blocks/
│
├── node_connect/
│
├── resource_balance/
│
├── machine_configuration/
│
└── npc_deduction/
```

Cada archetype debe proporcionar idealmente:

```text
validate()
compile()
solve()
simulate()
reset()
serialize()
deserialize()
```

---

# 39. WORLDSTATE

Debe existir un estado centralizado o claramente controlado.

Ejemplo:

```json
{
  "player": {},
  "regions": {},
  "quests": {},
  "puzzles": {},
  "npcs": {},
  "inventory": {},
  "flags": {},
  "knowledge": {},
  "bkt": {}
}
```

Los sistemas no deberían inventar estados paralelos incompatibles.

---

# 40. EVENT BUS

Una evolución recomendable:

```text
PuzzleSolved
PuzzleFailed
QuestStarted
QuestCompleted
NPCInteracted
RegionEntered
ItemCollected
BossPhaseCompleted
KnowledgeDemonstrated
```

Ejemplo:

```text
PuzzleSolved
      ↓
WorldState
      ↓
QuestSystem
      ↓
DoorSystem
      ↓
DialogueSystem
      ↓
BKT
```

Esto evita dependencias rígidas.

---

# 41. BKT / APRENDIZAJE

MindCrafted no solamente debe registrar:

```text
puzzle solved = true
```

También debe relacionar acciones con conceptos.

Ejemplo:

```json
{
  "concept": "network_routing",
  "evidence": {
    "attempts": 3,
    "hintsUsed": 1,
    "solutionQuality": 0.82
  }
}
```

El aprendizaje puede afectar contenido futuro.

---

# 42. ADAPTACIÓN

Posteriormente se puede usar BKT para modificar:

```text
difficulty
number of constraints
hint delay
boss composition
NPC assistance
optional challenges
```

Pero el sistema de adaptación NO debe cambiar reglas arbitrariamente durante un puzzle de forma injusta.

Preferir adaptación entre puzzles.

---

# 43. EXPERIENCIA DEL JUGADOR

Cada región debería intentar seguir:

```text
EXPLORAR
   ↓
DESCUBRIR
   ↓
OBSERVAR
   ↓
EXPERIMENTAR
   ↓
FALLAR
   ↓
ENTENDER
   ↓
RESOLVER
   ↓
CAMBIO DEL MUNDO
   ↓
RECOMPENSA NARRATIVA
   ↓
NUEVO DESAFÍO
```

---

# 44. NO CONSTRUIR MÁS ESCENARIOS VACÍOS

No priorizar cantidad de mapas.

Antes de añadir muchas zonas, asegurar:

```text
1 región
+
NPC
+
quest
+
3 mecánicas diferentes
+
boss
+
save
+
BKT
+
tests
```

funcionando correctamente.

Después escalar.

---

# 45. PRIORIDAD DE DESARROLLO

## FASE V2.1

Terminar los pilares de puzzles.

Implementar:

```text
node_connect
resource_balance
machine_configuration
```

Cada uno con:

```text
schema
validator
compiler
solver
simulation
reset
persistence
unit tests
E2E
```

---

# 46. FASE V2.2

Implementar:

```text
MULTIPHASE BOSS SYSTEM
```

Boss compuesto por:

```text
2-4 archetypes
```

y conceptos anteriores.

---

# 47. FASE V2.3

Implementar:

```text
AGENT TOOL CALLING
+
STRUCTURED OUTPUTS
```

El agente utiliza exclusivamente herramientas seguras.

---

# 48. FASE V2.4

Implementar:

```text
DYNAMIC NPC
+
CONTEXTUAL HINTS
+
ADAPTIVE DIFFICULTY
```

---

# 49. FASE V2.5

Aumentar variedad:

```text
classification_zones
collect_assemble
spatial_order
timeline_path
hazard_pattern
npc_deduction
logic_circuit
dependency_graph
```

---

# 50. DEFINITION OF DONE PARA UN NUEVO ARCHETYPE

Una nueva mecánica NO se considera terminada solamente porque puede jugarse.

Debe incluir:

- [ ] schema definido;
- [ ] validación;
- [ ] compilador;
- [ ] representación world-native;
- [ ] solver;
- [ ] reset;
- [ ] manejo de failure;
- [ ] anti-softlock;
- [ ] persistencia;
- [ ] consecuencia del mundo;
- [ ] integración educativa;
- [ ] unit tests;
- [ ] simulation tests;
- [ ] random-action tests;
- [ ] E2E;
- [ ] integración con AI generator;
- [ ] integración con QualityGate.

---

# 51. DEFINITION OF DONE PARA UN MUNDO GENERADO

Una campaña generada se publica solamente si:

- [ ] Blueprint válido.
- [ ] Todas las referencias existen.
- [ ] Todos los puzzles obligatorios son world-native.
- [ ] No hay overlays obligatorios.
- [ ] No hay iframe obligatorio.
- [ ] Todos los puzzles tienen solución.
- [ ] No existen softlocks conocidos.
- [ ] Cada puzzle produce consecuencias.
- [ ] Los conceptos académicos afectan las mecánicas.
- [ ] El contenido está grounded.
- [ ] Los diálogos no revelan soluciones directamente.
- [ ] El personaje puede recorrer el mundo.
- [ ] Collision funciona.
- [ ] Quests funcionan.
- [ ] Persistence funciona.
- [ ] BKT no duplica eventos.
- [ ] E2E pasa.
- [ ] QualityGate determinista pasa.
- [ ] AI Judge pasa.

---

# 52. REGLAS PARA ASTRA AL MODIFICAR EL PROYECTO

Antes de implementar algo Astra debe preguntarse internamente:

### 1.

¿Estoy trabajando sobre V2 o estoy extendiendo accidentalmente V1?

### 2.

¿Esta funcionalidad mantiene al jugador dentro del mundo?

### 3.

¿Estoy dejando que la IA tome una decisión que debería tomar el runtime?

### 4.

¿Puedo expresar esto mediante un Blueprint/schema?

### 5.

¿Existe una forma determinista de probarlo?

### 6.

¿Puede producir softlock?

### 7.

¿Puede guardarse y restaurarse?

### 8.

¿El concepto académico afecta realmente a la mecánica?

### 9.

¿Estoy creando otra variante de algo que ya existe?

### 10.

¿Este cambio acerca MindCrafted a un RPG educativo o a una colección de quizzes?

Si la respuesta a la última pregunta es:

```text
colección de quizzes
```

detenerse y rediseñar.

---

# 53. REGLA PARA REFACTORIZACIONES

Astra NO debe hacer grandes reescrituras innecesarias.

Antes de reemplazar código existente:

1. analizarlo;
2. identificar qué parte ya funciona;
3. crear tests;
4. realizar cambios pequeños;
5. mantener compatibilidad cuando sea razonable;
6. migrar gradualmente hacia V2.

Preferir:

```text
EVOLUTION
```

sobre:

```text
TOTAL REWRITE
```

---

# 54. REGLA PARA CÓDIGO LEGACY

Si se encuentra algo como:

```text
launchMiniGame()
mini-game-overlay
iframe game
old generated HTML minigame
```

NO eliminar automáticamente sin investigar.

Primero identificar:

- quién lo usa;
- si pertenece a V1;
- si existen tests;
- si una ruta V2 todavía depende de él.

Luego migrar.

El objetivo final sí es que World V2 no dependa de estos sistemas.

---

# 55. REGLA DE TEST ANTES DE REFACTOR

Si Astra detecta una parte importante sin tests:

ANTES DE CAMBIARLA:

```text
escribir characterization tests
```

Después refactorizar.

---

# 56. REGLA PARA IA

Nunca asumir que una salida de IA es correcta.

Toda salida atraviesa:

```text
LLM OUTPUT
    ↓
PARSE
    ↓
SCHEMA
    ↓
SEMANTIC VALIDATION
    ↓
COMPILER
    ↓
SOLVER
    ↓
SIMULATION
    ↓
TESTS
    ↓
QUALITY GATE
```

---

# 57. MANIFIESTO DEL PROYECTO

MindCrafted no quiere utilizar IA simplemente para decir:

> Tenemos IA.

La IA existe para permitir que cada material educativo pueda convertirse en una experiencia jugable distinta.

El runtime determinista existe para garantizar que esa experiencia siga siendo:

- jugable;
- solucionable;
- segura;
- coherente;
- educativa;
- verificable.

La combinación es:

```text
CREATIVITY
     +
DETERMINISM
     =
MINDCRAFTED
```

---

# 58. OBJETIVO FINAL

Un estudiante debería poder cargar material sobre:

```text
Redes
Bases de Datos
Sistemas Operativos
Matemática
Historia
Logística
Programación
Electrónica
```

y obtener algo que se sienta como:

```text
UN PEQUEÑO RPG DISEÑADO PARA ESE MATERIAL
```

y NO como:

```text
un cuestionario con un personaje caminando alrededor.
```

---

# 59. EJEMPLO FINAL

Material:

```text
Redes de computadoras
Routing
Congestión
Balanceo
```

Experiencia generada:

```text
REGIÓN
Centro de comunicaciones abandonado

NPC
Ingeniera atrapada en una sala de control

PROBLEMA
La red colapsó.

PUZZLE 1
node_connect

El jugador debe reconstruir físicamente enlaces.

PUZZLE 2
route_network

Debe enviar paquetes sin utilizar nodos dañados.

PUZZLE 3
resource_balance

Debe distribuir tráfico evitando saturación.

CAMBIO DEL MUNDO
Se restauran luces.
Se abre el ascensor.

BOSS
Ataque de tráfico.

FASE 1
Routing.

FASE 2
Balanceo.

FASE 3
Congestión dinámica.

RESULTADO
El centro vuelve a funcionar.

NPC
Reconoce que el estudiante comprendió el sistema.

BKT
Actualiza mastery de:

routing
load_balancing
congestion
```

Este es el estándar al que MindCrafted debe aspirar.

---

# 60. INSTRUCCIÓN FINAL PARA ASTRA

Astra:

No optimices MindCrafted para producir la mayor cantidad posible de minijuegos.

Optimízalo para producir:

> mundos pequeños, coherentes, difíciles, educativos y verificables donde aprender cambie literalmente el mundo que rodea al jugador.

Cuando exista una elección entre:

```text
más contenido
```

y:

```text
mejor integración
```

priorizar:

```text
MEJOR INTEGRACIÓN
```

Cuando exista una elección entre:

```text
más libertad para la IA
```

y:

```text
runtime verificable
```

priorizar:

```text
RUNTIME VERIFICABLE
```

Cuando exista una elección entre:

```text
quiz sencillo
```

y:

```text
mecánica que representa el concepto
```

priorizar:

```text
MECÁNICA
```

MindCrafted 2.0 debe sentirse primero como un buen videojuego.

Y precisamente a través de ese videojuego:

el estudiante debe aprender.