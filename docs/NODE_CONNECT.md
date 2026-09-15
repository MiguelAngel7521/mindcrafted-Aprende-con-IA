# node_connect — World V2

Implementación incremental bajo `AGENTS.md` §58 y `MINDCRAFTED_V2_ASTRA.md`.
El alumno construye dependencias dirigidas entre componentes físicos; las funciones
académicas de esos componentes determinan los enlaces admisibles. No hay pregunta
posterior, iframe, overlay de minijuego ni un segundo canvas.

## Arquitectura e interfaces

Se extiende el pipeline canónico y se conservan los reproductores/tests legacy.
La única implementación nueva de reglas es un módulo puro en cada lenguaje;
se comprueba exhaustivamente su equivalencia. No se introduce otro WorldEngine.

| Operación | Implementación |
| --- | --- |
| Schema | `world_schema.NodeConnect`, unión `Mechanics` de PuzzleBlueprint/PuzzleSpec |
| `validate()` | `generator/node_connect.py`, más evidencia/referencias/espacio en `world.validate_world()` |
| `compile()` | `world.compile_puzzle_spec()` y `compile_world()`: entidades, consola, NPC, quest, puerta |
| `solve()` | `node_connect.solve()`, mediante el dispatcher existente `world_solver.solve_puzzle()` |
| `simulate()` | `node_connect.simulate()` y `engine/world/node-connect.js::nodeConnectResult()` |
| Runtime | `WorldEngine.interact()/assess()` y renderer principal `runtime.js` |
| `reset()` | `WorldEngine.reset()`, manual o recuperación automática tras fallo |
| `serialize()/deserialize()` | `WorldEngine.snapshot()/restore()` y `SaveSystem.save()/load()`; JSON local existente |
| Consecuencias | EventBus, FlagSystem, QuestSystem y DialogueSystem existentes |
| Generación/QualityGate | `world_pipeline.generate_campaign()` y `world_package.quality_gate()` existentes |

## Schema final

Definición completa, con `additionalProperties: false` y límites:
[`node-connect.schema.json`](../mindcrafted/engine/world/node-connect.schema.json).
También forma parte de `world-v2.schema.json` y `campaign-v2.schema.json`.

```text
mechanics = {
  archetype: "node_connect",
  schemaVersion: 1,
  nodes: [{id, label, kind}],                       // 3..8
  edges: [{id, source, target}],                    // 2..12
  connectionRules: [                               // 1..12, unión discriminada
    {kind: "compatible", allowed: [{sourceKind, targetKind}], ruleId},
    {kind: "degree", node, direction: "in"|"out", min, max, ruleId},
    {kind: "acyclic", ruleId}
  ],
  goals: [{source, target, ruleId}]                 // 1..8 caminos dirigidos
}
```

`label` es representación; `kind` es función conceptual. `edges` incluye todos los
enlaces que el alumno puede construir, incluso distractores incompatibles. Las
reglas distinguen cuáles son académicamente válidos. Todas las restricciones y
metas deben cumplirse; un grafo vacío nunca resuelve.

El conocimiento permanece en `knowledge.concept`, `learning_action` y
`requiredRules[{id, skill, description, evidence}]`. Cada `ruleId` debe existir,
y cada regla educativa debe afectar al menos una restricción o meta. El grafo de
conocimiento vincula esas reglas a `/mechanics/connectionRules/<índice>` o
`/mechanics/goals/<índice>` y conserva citas verificadas de la fuente.

El compilador añade el contrato existente: `runtime: world`, `mandatory`,
`world.anchorEntity`, `resettable`, dificultad, fracaso y
`success{setFlags, openEntity, dialogue, xp}`. El modelo propone el puzzle y su
contexto; las referencias de entidades y efectos críticos las construye el código.
Ejemplo completo reproducible: `generator/node_connect_demo.py::blueprint()`.

## Solver y acoplamiento educativo

El solver enumera todos los subconjuntos de enlaces: como máximo `2^12 = 4096`.
Cada grafo se somete a compatibilidad por tipos, grados entrantes/salientes,
ausencia de ciclos cuando se exige y alcance dirigido de cada meta. No basta
encontrar una ruta ignorando el resto del grafo.

Devuelve una solución mínima en enlaces, acciones reproducibles, número total de
soluciones y hasta tres alternativas. El compilador convierte cada acción en un
recorrido físico y verifica colisiones, acceso, misiones y puertas. Node reproduce
el recorrido con el motor real y Playwright lo ejecuta mediante teclado.

Cada `requiredRule` pasa una prueba de ablación: quitarla debe permitir al menos
un grafo que antes fallaba. Se rechazan reglas prescindibles, ausencia de
distractores incompatibles, grafos insolubles, conectar todo para ganar y más de
un 10 % de configuraciones válidas. HARD exige al menos seis interacciones;
en este archetype, dos interacciones por enlace y una para enviar implican al
menos tres enlaces.

El ejemplo HARD usa cinco nodos y once enlaces: **4 soluciones de 2048 grafos**,
dos mínimas de tres enlaces, **7 interacciones**, `randomSuccessProbability =
0.001953125` (0,1953125 %). `randomSuccessRate = 3/256 = 0.01171875`
(1,171875 %) para la muestra uniforme con seed `20260914`.
Se distinguen la probabilidad exacta y la estimación de una muestra pequeña.
Otra prueba usa seed `271828`, 256 secuencias de 1..24 conexiones/desconexiones,
y verifica fallo, recuperación y solución posterior en el WorldEngine real.

La ablación prueba causalidad formal, no verdad académica ni calidad didáctica.
El juez existente debe rechazar etiquetas arbitrarias, contenido decorativo y
soluciones reveladas en el diálogo inicial. Su PASS jamás revoca un fallo
determinista. La publicación exige ambas evaluaciones.

## Interacción, recuperación y persistencia

1. Hablar con Luna activa la quest sin abandonar el mapa.
2. E junto a un componente selecciona el origen; caminar a otro y pulsar E
   alterna ese enlace dirigido. Seleccionar de nuevo el origen cancela.
3. Repetir un par desconecta. Un destino sin enlace físico posible no destruye
   conexiones; permite elegir otro destino, cancelar o reiniciar.
4. E junto a la consola evalúa. Un fallo conserva feedback del último intento
   y limpia los enlaces para reconstruir. R limpia también el feedback.
5. Los cables y nodos cambian de color dentro del mismo canvas; las curvas
   separan direcciones opuestas y evitan aparentar conexiones intermedias.
6. Resolver activa `layers_restored`, restaura la infraestructura, abre la
   compuerta, completa `layers_quest` y cambia el diálogo de Luna. Su reflexión
   registra `layers_understood`. XP es un efecto adicional.

El guardado conserva conexiones parciales, origen seleccionado, intento fallido,
solución, flags, quest y observaciones educativas. Al cargar se filtran IDs
inválidos, se reevalúa el grafo y se reconstruyen flags y recompensas desde una
solución comprobada. No se confía en un `solved` o efecto falsificado.
Reload no emite nuevas observaciones BKT ni vuelve a otorgar XP/inventario.

BKT registra por regla el resultado de cada envío, intentos, errores/acciones
válidas e inválidas, pasos, pistas, reinicios y tiempo. Las ayudas son progresivas;
la primera pista es conceptual y la solución escrita queda en el nivel final.

## Generación y evidencia

`WORLD_DESIGN_SYSTEM` explica el contrato y `BLUEPRINT_SCHEMA` lo incluye.
`generate_campaign()` conserva el proveedor configurable y los tres intentos
máximos de reparación existentes. La IA aporta datos: nodos, roles, enlaces,
restricciones, metas, conocimiento y diálogo. Nunca se ejecuta su código.
No se añadió Structured Outputs ni una nueva Agent API.

El test de generación usa un proveedor simulado: primero produce una referencia
rota, recibe el diagnóstico, la repara y solo llega al juez tras superar solver,
runtime y Chromium reales. Otro test proporciona un juez perfecto a un grafo
insoluble y verifica que la publicación sea rechazada.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m mindcrafted.generator.world_tools check --archetype node_connect --output output/node-connect
```

`output/node-connect/index.html` es una demo portable sin API.
`validation.json` contiene pruebas y métricas reales. **`approved: false`,
`judge: null`** indica que esta demo no llamó a un juez externo; los seis controles
deterministas pasan. No se presenta un juez simulado como aprobación pedagógica.
Las capturas parciales, de fallo, restauración y móvil y `node-connect-e2e.json`
se conservan en esa carpeta después de la ejecución final.

Pruebas propias:

- `tests/test_node_connect_solver.py`: schema/referencias, límites, múltiples
  soluciones, ciclos, grados, datos de estado inválidos y rechazo de trivialidad.
- `tests/test_node_connect_integration.py`: KnowledgeGraph, paridad exhaustiva
  Python/JS, recuperación aleatoria, persistencia, recompensas, generación y veto
  del solver. Incluye campaña mixta con route_network y repetición de IDs entre
  regiones para verificar aislamiento y recargas.
- `tests/test_node_connect_browser.py`: NPC → quest → fallo → recuperar → solución
  alternativa → consecuencia → NPC → reload, teclado real, escritorio y móvil.
  El observador detecta iframe/overlay/canvas temporal, mundo oculto o sustituido,
  y cambio de WorldEngine durante el puzzle. Un cambio declarado de región conserva
  la identidad del canvas y el historial de violaciones.

Resultado final ejecutado: **248 tests pasando**, cero fallos;
incluye el bloque inicial de World V2, el contrato de proveedor real y las pruebas
de protección BYOK. Se conservan las cuatro advertencias de deprecación de
`FastAPI.on_event` ya presentes en el baseline.
El registro JUnit está en `output/node-connect/tests.xml`.
También pasaron `git diff --check`, `node --check` para los tres módulos JS
modificados de la mecánica y `compileall` del generador. El comando de demo/check
terminó con sus seis controles deterministas en `true` y sin errores.

## Archivos del bloque y límites

Nuevos: `generator/node_connect.py`, `generator/node_connect_demo.py`,
`engine/world/node-connect.js`, `engine/world/node-connect.schema.json`, los tres
tests anteriores y este documento.

Extendidos: `generator/world_schema.py`, `world.py`, `world_solver.py`,
`world_knowledge.py`, `world_package.py`, `world_continuity.py`, `world_tools.py`,
`prompts.py`; `engine/world/core.js`, `runtime.js`, `player.html`, los schemas
`world-v2.schema.json` y `campaign-v2.schema.json`; `docs/WORLD_V2.md`.
Los cuatro sistemas compartidos ya pertenecían a la consolidación aceptada.

La feature cubre los 17 puntos de la DoD de archetype (§58). La aprobación de un
mundo generado (§59) continúa requiriendo un juez real PASS. No se hizo una llamada
de pago ni se afirma validación con estudiantes. Los grafos se limitan a ocho
nodos y doce enlaces dirigidos; no incluyen puertos, pesos ni circuitos analógicos.
El layout sigue siendo el compilador por distritos existente. La dificultad
estadística no demuestra resistencia a cualquier estrategia de ensayo y error.

Siguiente paso recomendado: evaluar una campaña producida por un proveedor real
con material académico y su juez, antes de ampliar los archetypes. No se adelantó
`resource_balance` en aquel bloque, bosses nuevos, NPC dinámicos ni otras capas de generación.
Actualización: `resource_balance` y `machine_configuration` ya están implementados;
ver [WORLD_V2.md](WORLD_V2.md) para el estado de los tres pilares.
