# AGENTS.md — MindCrafted 2.0

> Dirección obligatoria para Codex y agentes que modifiquen este repositorio.

## 1. Antes de tocar código

Lee primero:

- `DOCUMENTACION_PROYECTO.md`
- `mindcrafted/server.py`
- `mindcrafted/generator/course_pipeline.py`
- `mindcrafted/generator/pipeline.py`
- `mindcrafted/generator/api.py`
- `mindcrafted/generator/prompts.py`
- `mindcrafted/generator/assembler.py`
- `mindcrafted/generator/sandbox.py`
- `mindcrafted/engine/player.html`
- `mindcrafted/engine/engine.js`
- `mindcrafted/engine/bkt.js`

`DOCUMENTACION_PROYECTO.md` describe V1. Este archivo define la dirección de **MindCrafted 2.0**.

No reescribas todo. Migra incrementalmente, preserva lo que funciona y añade tests.

---

# 2. North Star

MindCrafted 2.0 NO es:

```text
material → diálogo → minijuego externo → diálogo → fin
```

Debe ser:

```text
material educativo
      ↓
aventura jugable
      ↓
personaje explora el mundo
      ↓
NPC / objeto / problema
      ↓
puzzle integrado físicamente al mapa
      ↓
el jugador aplica conocimiento
      ↓
el mundo cambia
      ↓
nueva ruta / diálogo / quest / consecuencia
      ↓
BKT registra aprendizaje
```

Objetivo: un RPG educativo desafiante con exploración, diálogo, puzzles y consecuencias integradas. Puede inspirarse en la sensación de progresión de juegos narrativos como Undertale, pero no copiar personajes, arte, historia, mapas, música ni contenido protegido.

De `edgameclaw`, aprovechar principalmente la filosofía:

```text
analizar → diseñar interacción → generar → juzgar → reparar
```

No copiar el patrón de minijuegos aislados en overlays.

---

# 3. Regla principal

## PUZZLES LIVE IN THE WORLD

Por defecto está prohibido:

```text
mundo
→ launchMiniGame()
→ modal/overlay/iframe/pantalla aparte
→ minijuego
→ volver al mundo
```

Para puzzles V2 no usar como arquitectura principal:

- `mini-game-overlay`
- modal de quiz
- iframe de minijuego
- segunda pantalla desconectada
- canvas independiente que sustituye el mundo
- opción múltiple como puzzle obligatorio

Un puzzle válido debe estar anclado a una entidad o región:

```text
jugador → consola → puzzle dentro del mapa
                    ↓
            cambia el estado del mundo
                    ↓
          puerta/ruta/NPC se modifica
```

Puede bloquearse temporalmente el movimiento durante una interacción, pero el jugador debe seguir visual y conceptualmente dentro del mismo mundo.

---

# 4. El jugador es parte central

La vertical slice V2 debe tener un personaje realmente controlable.

Mínimo:

- WASD y flechas
- dirección/facing
- colisiones
- interacción con `E`, `Enter` o equivalente
- cámara
- spawn
- NPC
- puertas/objetos
- recuperación del control tras diálogo
- posición serializable
- recarga conservando progreso seguro

El gameplay principal no debe depender únicamente del mouse.

---

# 5. La IA diseña; el código decide

Regla no negociable:

> El LLM NO decide en tiempo real si el jugador ganó.

La IA puede generar:

- `KnowledgeGraph`
- regiones
- quests
- NPC
- diálogos
- `PuzzleBlueprint`
- hints
- dificultad
- narrativa
- consecuencias
- criterios declarativos de éxito

El runtime determinista evalúa:

- movimiento
- colisiones
- secuencias
- conexiones
- recursos
- reglas
- condiciones de éxito
- fallos
- flags
- progreso
- BKT

Una campaña generada debe poder jugarse y terminarse sin conexión a una IA.

---

# 6. Evitar JavaScript arbitrario generado

V2 debe migrar hacia:

```text
IA
 ↓
PuzzleBlueprint JSON
 ↓
JSON Schema
 ↓
PuzzleCompiler
 ↓
PuzzleSpec
 ↓
PuzzleRuntime determinista
```

No:

```text
IA → string JavaScript → eval/inyección
```

Los puzzles normales deben usar especificaciones declarativas y componentes confiables.

Un futuro modo `custom_world_puzzle` puede existir solo si tiene:

- feature flag
- contrato
- sandbox
- timeout
- QualityGate
- tests
- fallback
- acceso restringido a DOM/red/storage

No es prioridad para la primera vertical slice.

---

# 7. Arquitectura objetivo

```text
SOURCE
  ↓
KnowledgeExtractor
  ↓
KnowledgeGraph
  ↓
WorldPlanner
  ↓
QuestPlanner
  ↓
PuzzleDesigner
  ↓
PuzzleCompiler
  ↓
DeterministicValidators
  ↓
AIJudge
  ↓
RepairLoop
  ↓
CampaignAssembler
  ↓
WorldPackage
  ↓
WorldEngine
```

Separación sugerida:

```text
mindcrafted/generator/v2/
├── knowledge.py
├── world_planner.py
├── quest_planner.py
├── puzzle_designer.py
├── puzzle_compiler.py
├── dialogue_generator.py
├── quality_gate.py
├── ai_judge.py
├── repair.py
└── campaign_pipeline.py

mindcrafted/contracts/
├── world.schema.json
├── region.schema.json
├── quest.schema.json
├── dialogue.schema.json
└── puzzle.schema.json

mindcrafted/engine/world/
├── world-engine.js
├── player-controller.js
├── collision-system.js
├── camera-system.js
├── entity-system.js
├── dialogue-system.js
├── puzzle-runtime.js
├── quest-system.js
├── flag-system.js
├── inventory-system.js
├── event-bus.js
└── save-system.js
```

Los nombres pueden adaptarse al código existente. La separación de responsabilidades sí debe preservarse.

---

# 8. Sistemas del runtime

`WorldEngine` debe coordinar:

- game loop
- render/update
- player
- input
- mapa
- cámara
- colisiones
- entidades
- triggers
- puzzles
- diálogos
- quests
- transición de regiones

No convertir `engine.js` en un archivo monolítico cada vez mayor.

Usar un `EventBus` o equivalente:

```javascript
events.emit("puzzle.started", { puzzleId: "router-01" });
events.emit("puzzle.failed", { puzzleId: "router-01" });
events.emit("puzzle.solved", { puzzleId: "router-01", attempts: 2 });
events.emit("world.flag.set", { flag: "north_gate_open", value: true });
```

Evitar acoplamientos directos entre sistemas si pueden comunicarse por eventos.

---

# 9. Consecuencias obligatorias

Todo puzzle obligatorio debe cambiar el mundo de forma observable.

Ejemplos:

- abrir puerta
- activar ascensor
- encender energía
- cambiar iluminación
- mover plataforma
- reparar máquina
- cambiar diálogo de NPC
- abrir ruta
- retirar obstáculo
- entregar objeto
- revelar región
- activar una quest

`+100 XP` puede existir, pero NO puede ser la única consecuencia.

---

# 10. Diálogos world-native

Los diálogos deben activarse por eventos del mundo:

- proximidad
- interacción
- flag
- quest
- puzzle iniciado
- puzzle fallido
- puzzle resuelto
- objeto obtenido
- región descubierta

Preferir:

```text
contexto → observación → reto → experimento → consecuencia → reflexión
```

No revelar la solución antes de que el jugador experimente el problema.

Ejemplo declarativo:

```json
{
  "id": "mentor_after_router",
  "trigger": {
    "event": "puzzle.solved",
    "puzzleId": "router-balance"
  },
  "speaker": "mentor",
  "lines": [
    {
      "speaker": "mentor",
      "text": "No hiciste los paquetes más rápidos. Evitaste que todos compitieran por la misma ruta."
    }
  ]
}
```

---

# 11. PuzzleBlueprint y PuzzleSpec

La IA primero genera intención pedagógica:

```json
{
  "id": "router-balance",
  "concept": "congestión y balance de rutas",
  "learningAction": "distribuir tráfico entre rutas limitadas",
  "archetype": "route_network",
  "mandatory": true,
  "worldAnchor": "router_console",
  "difficulty": "hard",
  "requiredRules": [
    "cada enlace tiene capacidad limitada",
    "una ruta saturada pierde paquetes"
  ]
}
```

`PuzzleCompiler` lo transforma a un `PuzzleSpec` ejecutable:

```json
{
  "id": "router-balance",
  "runtime": "world",
  "archetype": "route_network",
  "mandatory": true,
  "knowledge": {
    "concept": "congestión de red",
    "learningAction": "balancear tráfico",
    "requiredRules": []
  },
  "world": {
    "region": "network_city",
    "anchorEntity": "router_console"
  },
  "success": {
    "setFlags": ["district_network_online"],
    "openEntity": "north_gate",
    "xp": 75
  },
  "failure": {
    "autoReset": true,
    "hintAfterAttempts": 3
  },
  "difficulty": {
    "level": "hard",
    "minSolutionSteps": 6,
    "maxSolutionSteps": 20,
    "randomSuccessProbabilityMax": 0.15
  }
}
```

Todo spec generado debe validar antes de llegar al navegador.

---

# 12. Archetypes

Primera biblioteca estable:

1. `switch_sequence`
2. `route_network`
3. `push_blocks`

Luego:

- `node_connect`
- `classification_zones`
- `resource_balance`
- `collect_assemble`
- `spatial_order`
- `timeline_path`
- `machine_configuration`
- `hazard_pattern`
- `npc_deduction`

Un archetype es genérico. No incrustar una materia específica en su runtime.

Ejemplo: `route_network` puede representar redes, circulación, logística, electricidad o transporte.

Cada archetype estable debe tener equivalente a:

```python
validate(spec)
solve(spec)
simulate(spec)
```

`solve()` debe demostrar que existe solución cuando el tipo de puzzle lo permita.

`simulate()` debe buscar estados límite y softlocks.

---

# 13. Regla pedagógica crítica

RECHAZAR un puzzle cuando:

> el concepto educativo podría eliminarse sin cambiar significativamente cómo se resuelve.

MAL:

```text
Pregunta: ¿qué es TCP?
Respuesta correcta → abre puerta
```

BIEN:

```text
El jugador manipula un sistema donde confiabilidad,
orden y confirmación cambian el comportamiento de los paquetes.
```

El conocimiento debe conducir la mecánica.

---

# 14. Evitar quizification

No usar como núcleo de una región:

- multiple choice
- true/false
- definiciones escritas
- flashcards
- matching puramente textual
- preguntas usadas como contraseña

Pueden aparecer como actividad secundaria ocasional.

Los puzzles obligatorios deben exigir interacción con sistemas.

---

# 15. Dificultad

MindCrafted debe poder generar un juego difícil, pero justo.

Dificultad significa:

- más pasos
- combinar reglas
- observar consecuencias
- transferir conocimiento
- administrar restricciones
- reconocer patrones
- recuperar conceptos previos

No significa:

- texto confuso
- ambigüedad
- trampas
- memorización arbitraria

Progresión:

```text
INTRO: 1 regla
 ↓
APLICACIÓN: regla + distracción
 ↓
COMBINACIÓN: 2 reglas
 ↓
TRANSFERENCIA: misma idea en nuevo contexto
 ↓
BOSS: 2-4 conceptos anteriores juntos
```

Para puzzles `hard`, como objetivo orientativo:

```text
minSolutionSteps >= 6
randomSuccessProbability <= 0.15
requiredRules >= 1
```

No aplicar métricas que no tengan sentido para un archetype.

---

# 16. Boss puzzles

Los mejores puzzles deben ser “boss puzzles”.

Deben:

- integrar conceptos previos
- requerir múltiples acciones
- tener feedback visual
- permitir fallar
- permitir recuperarse
- tener solución verificable
- no resolverse fácilmente por azar
- tener pistas graduales
- cambiar significativamente el mundo
- producir reflexión narrativa posterior

Objetivo:

> demostrar comprensión, no reconocer una definición.

---

# 17. Fallo y anti-softlock

El jugador debe poder equivocarse.

Consecuencias válidas:

- congestión
- sobrecarga
- pérdida temporal de recursos
- máquina detenida
- ruta bloqueada temporalmente
- NPC reacciona
- pérdida de bonus

Pero ningún error normal puede dejar un puzzle obligatorio permanentemente irresoluble.

Todo puzzle obligatorio debe:

- reiniciarse;
- recuperarse;
- o garantizar retorno a un estado solucionable.

---

# 18. BKT

Conservar Bayesian Knowledge Tracing y hacerlo más granular.

No registrar solo:

```text
score = 70
```

Registrar observaciones:

```json
{
  "skill": "network.routing",
  "observations": {
    "correctActions": 8,
    "invalidActions": 3,
    "hintsUsed": 1,
    "attempts": 2,
    "solutionSteps": 10,
    "solutionTimeMs": 82000
  }
}
```

BKT debe poder representar concepto/regla/puzzle y no quedar acoplado a una UI concreta.

---

# 19. Agent API / orquestación

El agente debe operar desde backend.

Herramientas conceptuales:

```text
analyze_material
build_knowledge_graph
design_region
design_quest
design_puzzle_blueprint
compile_puzzle_spec
validate_world
solve_puzzle
judge_puzzle
repair_puzzle
generate_dialogue
package_campaign
```

La implementación puede usar tool calling o equivalente.

No acoplar WorldEngine a un proveedor concreto.

No enviar API keys al runtime del juego.

---

# 20. QualityGate

Ningún puzzle generado por IA se publica directamente.

```text
candidate
 ↓
JSON Schema
 ↓
Reference Validation
 ↓
World Validation
 ↓
Solver
 ↓
Anti-softlock
 ↓
Educational Checks
 ↓
AI Judge
 ↓
Runtime Test
 ↓
APPROVED
```

Si falla:

```text
report → RepairAgent → candidate nuevo → QualityGate
```

Máximo recomendado:

```text
3 reparaciones
```

Después usar un fallback prehecho seguro.

Tests deterministas SIEMPRE tienen autoridad sobre el AI Judge.

---

# 21. AI Judge

Puntuación sugerida:

| Criterio | Puntos |
|---|---:|
| aprendizaje integrado en la mecánica | 25 |
| integración con el mundo | 25 |
| calidad/diversión de interacción | 25 |
| completabilidad/calidad técnica | 25 |

Aprobar sugerido:

```text
>= 85/100
```

RECHAZAR si:

1. el concepto puede quitarse sin afectar solución;
2. es esencialmente un quiz;
3. ocurre fuera del mundo;
4. no cambia el mundo;
5. puede ganarse fácilmente al azar;
6. no hay solución demostrable;
7. hay softlock;
8. falta feedback;
9. contradice material educativo;
10. el LLM decide arbitrariamente si se ganó;
11. la instrucción regala la solución;
12. parece complejo pero tiene poca profundidad.

---

# 22. CampaignPackage V2

No destruir V1.

Agregar formato versionado, por ejemplo:

```text
campaign/
├── campaign.json
├── world.json
├── knowledge.json
├── quests.json
├── dialogues.json
├── puzzles/
├── regions/
└── assets/
```

Debe declarar algo equivalente a:

```json
{
  "format": "mindcrafted-campaign",
  "version": 2
}
```

El player debe distinguir V1/V2 mientras dure la migración.

---

# 23. API

Preservar inicialmente:

```http
POST /api/generate
GET /api/jobs/{job_id}
GET /api/courses/{course_id}/manifest
GET /play
```

Se pueden añadir rutas V2:

```http
POST /api/v2/generate
GET /api/v2/campaigns/{course_id}
GET /api/v2/campaigns/{course_id}/package
```

No romper contratos públicos existentes sin tests de compatibilidad.

---

# 24. Vertical Slice obligatoria

ANTES de generar mundos grandes, completar de extremo a extremo:

```text
1. jugador aparece
2. camina
3. colisiona
4. cámara funciona
5. encuentra NPC
6. dialoga
7. diálogo activa quest
8. recupera control
9. encuentra puzzle
10. puzzle ocurre EN EL MISMO MUNDO
11. puede fallar
12. puede reiniciar
13. puede resolver
14. resolver cambia el mundo
15. NPC cambia diálogo
16. BKT registra resultado
17. puerta/ruta se desbloquea
18. jugador atraviesa nueva ruta
19. progreso se guarda
20. recargar conserva estado
```

No pasar a generación masiva hasta que esto tenga E2E.

Primer puzzle recomendado: `switch_sequence`.

Primero probar runtime con contenido prehecho.
Después conectar generación por IA.

---

# 25. Orden de implementación

Salvo tarea explícita distinta:

```text
P0  WorldSpec/PuzzleSpec + schemas
P1  WorldEngine mínimo
P2  PlayerController
P3  colisiones + cámara
P4  NPC + diálogo world-native
P5  quests + flags
P6  switch_sequence dentro del mapa
P7  consequences + reset
P8  save/load
P9  BKT por acciones
P10 tests E2E
P11 PuzzleCompiler
P12 IA genera PuzzleBlueprint
P13 QualityGate + RepairLoop
P14 route_network
P15 push_blocks
P16 boss puzzle
```

No saltar a generación avanzada sin P0-P10 confiables.

---

# 26. Tests obligatorios

Debe existir un equivalente funcional a:

```python
def test_world_has_controllable_player(world):
    assert world["player"]["controllable"] is True
    assert world["player"]["spawnRegion"]


def test_every_puzzle_runs_inside_world(world):
    for puzzle in world["puzzles"]:
        assert puzzle["runtime"] == "world"


def test_every_puzzle_has_world_anchor(world):
    entities = collect_entities(world)
    for puzzle in world["puzzles"]:
        assert puzzle["world"]["anchorEntity"] in entities


def test_puzzle_changes_world_state(world):
    for puzzle in mandatory_puzzles(world):
        success = puzzle["success"]
        assert any([
            success.get("setFlags"),
            success.get("openEntity"),
            success.get("spawnEntity"),
            success.get("removeEntity"),
            success.get("unlockRegion"),
        ])


def test_mandatory_puzzle_is_recoverable(world):
    for puzzle in mandatory_puzzles(world):
        assert (
            puzzle.get("resettable") is True
            or puzzle.get("failure", {}).get("autoReset") is True
        )
```

Añadir además tests de:

- referencias inexistentes
- IDs
- schema
- solver
- random success
- anti-softlock
- diálogo
- flags
- quests
- save/load
- BKT
- compatibilidad V1

---

# 27. E2E

Cuando exista vertical slice suficiente, añadir Playwright.

Casos mínimos:

```text
spawn
movement
collision
NPC interaction
dialogue
quest activation
puzzle starts inside world
world remains visible
failure
reset
solution
door opens
NPC changes
BKT updates
reload persists
```

Para V2 debe verificarse que no aparece:

```text
#mini-game-overlay
```

ni una pantalla externa de minijuego.

En test/debug se puede exponer:

```javascript
window.__MINDCRAFTED_TEST__
```

con utilidades como:

```text
getPlayer()
teleportPlayer()
getFlag()
setFlag()
getEntity()
getPuzzleState()
solvePuzzleForTest()
resetPuzzle()
getQuest()
getBKT()
```

No habilitar cheats de debug en producción.

---

# 28. Seguridad

V2 debe reducir el JS generado.

Reglas:

- no `eval` para puzzles declarativos
- validar JSON
- validar IDs
- impedir path traversal
- limitar tamaños
- limitar solver
- limitar entidades/graphs
- no exponer API keys
- no permitir requests arbitrarios desde contenido generado
- no usar AI Judge como seguridad
- sandbox no sustituye aislamiento real

---

# 29. Material educativo = fuente de verdad

No inventar hechos educativos para hacer funcionar una mecánica.

Separar conceptualmente:

```text
SOURCE FACTS
DESIGN INFERENCE
NARRATIVE FICTION
```

La ficción ambienta el juego, pero no altera el contenido académico.

KnowledgeGraph debe conservar trazabilidad hacia el material fuente cuando sea posible.

Filosofía:

```text
concepto
→ comportamiento observable
→ sistema interactivo
→ puzzle
```

No:

```text
concepto → pregunta → opciones
```

---

# 30. Pistas

Pistas progresivas recomendadas:

```text
fallo 1 → feedback del sistema
fallo 2 → observación
fallo 3 → pista conceptual
fallo 4+ → pista más explícita
```

No entregar inmediatamente la solución exacta.

Las pistas deben usar el estado real del puzzle.

---

# 31. No hacer todavía

Antes de completar la vertical slice NO priorizar:

- React/Vue
- rediseño total del Studio
- base de datos
- cuentas
- multiplayer
- marketplace
- mundo infinito
- editor avanzado de mapas
- 20 archetypes
- combate complejo
- infraestructura distribuida

Primero demostrar:

```text
learning + world + puzzle + consequence
```

---

# 32. Anti-rewrite

Antes de crear un subsistema:

1. busca funcionalidad existente;
2. reutiliza lo útil;
3. extrae solo lo necesario;
4. mantiene compatibilidad;
5. añade tests;
6. migra por pasos.

No reemplazar todo `engine.js` de una vez si puede extraerse incrementalmente.

No crear implementaciones duplicadas sin justificación.

---

# 33. Definition of Done

Una feature está terminada cuando:

- cumple contrato
- tiene tests
- no rompe tests existentes
- maneja errores
- tiene fallback si depende de IA
- no introduce softlocks conocidos
- actualiza documentación si cambia arquitectura
- funciona en un flujo real

Un archetype está listo cuando tiene:

- schema
- renderer
- interacción
- éxito determinista
- fallo determinista
- reset
- validator
- solver cuando aplique
- simulation tests
- observaciones BKT
- world effects
- fixture
- unit tests
- E2E básico

---

# 34. Procedimiento para Codex

Antes:

1. lee este `AGENTS.md`;
2. lee archivos relacionados;
3. revisa tests;
4. entiende comportamiento existente.

Durante:

1. haz el cambio mínimo coherente;
2. no mezcles refactors no relacionados;
3. agrega tests con la feature;
4. prioriza determinismo.

Después ejecuta lo relevante:

```bash
python -m compileall mindcrafted
node --check mindcrafted/engine/engine.js
node --check mindcrafted/engine/bkt.js
pytest
```

Cuando existan:

```bash
pytest tests/v2
pytest tests/e2e
```

No ocultar tests fallidos.

Si una prueba no puede ejecutarse por el entorno, indicarlo.

Al terminar reportar:

```text
CAMBIOS
- ...

TESTS
- comando: resultado

RIESGOS / DEUDA
- ...

SIGUIENTE PASO
- ...
```

No afirmar que algo funciona sin verificarlo.

---

# 35. ¿Vamos por buen camino?

Antes de cerrar una tarea importante, comprobar:

### A
Si desconecto la IA después de generar la campaña,
¿puedo terminarla?

**Debe ser SÍ.**

### B
¿El puzzle ocurre donde el personaje lo encontró?

**Debe ser SÍ.**

### C
¿Resolverlo cambia el mundo?

**Debe ser SÍ** para puzzles obligatorios.

### D
¿Necesito aplicar el concepto académico?

**Debe ser SÍ.**

### E
¿Podemos demostrar que existe una solución?

**Debe ser SÍ** cuando el archetype permita solver.

### F
¿Una opinión del LLM decide si gané?

**Debe ser NO.**

---

# 36. Resultado buscado

Ejemplo con Redes:

```text
Ciudad de los Nodos
│
├── jugador explora
├── NPC informa problema
├── jugador investiga routers
├── puzzle de routing vive en el mapa
├── rutas malas producen congestión visible
├── jugador balancea tráfico
├── red vuelve a funcionar
├── cambia el entorno
├── NPC reacciona
├── BKT registra errores
└── se abre el siguiente distrito
```

Evitar:

```text
NPC habla
↓
quiz
↓
+100 XP
↓
NPC habla
```

---

# 37. Mantra

```text
1. WORLD FIRST.
2. PLAYER ALWAYS MATTERS.
3. PUZZLES LIVE IN THE WORLD.
4. AI DESIGNS; CODE DECIDES.
5. KNOWLEDGE DRIVES THE MECHANIC.
6. TEST BEFORE ACCEPTING GENERATED CONTENT.
```

Ésta es la dirección oficial de **MindCrafted 2.0**.
