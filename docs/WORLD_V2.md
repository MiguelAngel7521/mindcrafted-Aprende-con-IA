# MindCrafted 2.0: campañas continuas

Esta entrega implementa una región persistente por lección con jugador, colisiones,
cámara, NPC, misiones, diálogo asociado a eventos, puertas, reinicio, recompensas,
guardado y observaciones BKT por regla. `CampaignSession` conecta hasta 24 regiones
en el mismo canvas, con progreso independiente por lección y recompensas de campaña.
El jugador resuelve puzzles sobre el mapa.
La conversación se muestra debajo del mapa; no transporta al jugador a una arena.

## Ejecutar

```sh
.venv/bin/pip install -r requirements-dev.txt
# Chromium del sistema, o instalar el navegador de Playwright:
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q
.venv/bin/python -m mindcrafted.generator.world_tools demo --output output/world-demo
# Campaña de tres regiones, los tres arquetipos y boss de transferencia:
.venv/bin/python -m mindcrafted.generator.world_tools check --campaign --output output/campaign-demo
```

Abrir `output/world-demo/index.html`. Incluye los tres puzzles prehechos y los assets
necesarios para funcionar sin API ni servidor. WASD/flechas para caminar; E para
interactuar; R para reiniciar el puzzle actual; H para una pista; Esc para pausar.
También hay controles táctiles. Es una demo de desarrollo, **no una generación
aprobada por un juez IA**.
`output/campaign-demo/index.html` contiene la campaña completa y funciona sin IA,
servidor ni conexión. La salida de cada región activa la siguiente conservando el
canvas. `campaign.json` registra las comprobaciones reales; `world*.png` muestra
el inicio, las transiciones y el final en móvil.

```sh
# Genera capturas y un informe de pruebas reales, sin inventar una nota de IA:
.venv/bin/python -m mindcrafted.generator.world_tools check --output output/world-demo
```

El comando anterior puede terminar correctamente con `approved: false`: ejecuta
schema, worldGraph, solver, educational, runtime y E2E, pero no llama al juez.
`judge: not_run` explica la diferencia. La publicación normal exige todas las pruebas
y el juez; la exportación manual de la demo está separada de esa publicación.

## Contratos y arquetipos

`mindcrafted/engine/world/world-v2.schema.json` es el JSON Schema versionado.
`world_schema.py` es su definición tipada; un test exige que ambas coincidan.
Los objetos rechazan propiedades no declaradas. No hay campos para JS, HTML,
callbacks, imports, scripts ni ejecución de código proporcionado por el modelo.
Cada WorldSpec contiene exactamente una región, como exige su runtime. El contrato
`campaign-v2.schema.json` agrupa regiones, hashes y fuentes. IDs de puzzle repetidos
en distintas lecciones permanecen aislados.

| Arquetipo | Acción física | Árbitro determinista |
| --- | --- | --- |
| `switch_sequence` | Caminar hasta interruptores y energizar etapas | Restricciones de precedencia entre etapas |
| `route_network` | Cambiar cables en routers y enviar paquetes | Destino, ausencia de ciclos de entrega y capacidad acumulada |
| `push_blocks` | Empujar módulos hasta puestos con necesidades distintas | Movimiento, colisión y compatibilidad módulo→puesto |

El compilador coloca cada puzzle en un distrito de la región. La compuerta física
se abre al resolverlo; no se abre desde el diálogo ni por aprobación del LLM.
Un fallo reinicia los controles y conserva los intentos; R permite recuperar cajas
atascadas sin borrar misiones anteriores. Las pistas y la información de capacidad
están disponibles sin requerir llamadas de red.

Los solvers están acotados: hasta 7 interruptores, 4096 configuraciones completas de
rutas y 180000 estados de bloques. Un puzzle que excede el presupuesto se rechaza.
La prueba educativa elimina restricciones por `ruleId` y exige que cambie el conjunto
de soluciones. La evidencia debe aparecer literalmente en el material, normalizando
espacios y mayúsculas.

`randomSuccessProbability` mide soluciones válidas entre configuraciones completas
equiprobables (permutaciones de interruptores, elecciones de rutas o asignaciones de
bloques a metas). No pretende demostrar una probabilidad universal sobre cualquier
estrategia de clics. La evaluación semántica del juez sigue siendo necesaria: una
restricción causal por sí sola no demuestra calidad pedagógica ni diversión.

## Generación y publicación

El Studio envía `course.gameplay: world`. Se conserva `POST /api/generate`, el job,
la consulta del estado y `/api/play/{course}/{chunk}/package`. La generación rápida
de aventura usa el nuevo flujo por defecto; `world_native=False` permite usar el
generador anterior de forma explícita. Los paquetes ya existentes siguen usando
sus respectivos reproductores.

```text
Material + contexto
    → PuzzleBlueprint (reglas, evidencia, misión, mecánica y diálogos)
    → compilador WorldSpec v2
    → schema + referencias + solver + recorrido espacial + prueba educativa
    → reproducción del recorrido en Node con el motor real
    → Playwright/Chromium con entradas de teclado, recarga y móvil
    → juez IA: 4 categorías de 25 puntos, mínimo 85 y ninguna objeción
    → publicación del World Package
    → KnowledgeGraph con citas y posiciones en la fuente
    → contexto acotado para la siguiente lección
    → boss final que combina habilidades anteriores
    → composición de campaña + recorrido real entre regiones
```

Cada candidato pasa todos los controles deterministas antes de llegar al juez.
Hay hasta tres intentos de diseño/reparación. Un fallo determinista siempre veta la
publicación, incluso si el juez dice `approved: true`. El escritor vuelve a comprobar
el hash y el contrato después de la espera del juez.
El contexto entre lecciones se obtiene sin nuevas llamadas de IA: conserva hasta
12 reglas, 6000 caracteres de citas y 12000 caracteres JSON. Las citas de repaso
se incorporan al material efectivo sin superar 60000 caracteres. Esto describe
contenido presentado anteriormente; no afirma que el alumno ya lo domine.

`role: boss` exige de 2 a 4 habilidades previas, al menos seis acciones y las mismas
pruebas de causalidad, solución y recuperación. La última lección solicita este
rol. `difficulty: hard` también exige seis acciones verificables. El boss prehecho
transfiere capacidad y entrega a cinco emisores y tres routers; no añade combate.

El fallback solo reutiliza una versión previamente aprobada de **los mismos apuntes**,
con evidencia, hash, juez y pruebas nuevamente comprobados. Si no existe, el job
falla de forma explícita y no publica un puzzle ajeno al material.

Los tests de integración usan respuestas de modelo controladas y un juez simulado;
las pruebas del motor y navegador sí se ejecutan realmente. No se ha medido la tasa
de aprobación ni la calidad educativa de un proveedor LLM real en esta entrega.

La compatibilidad actual conserva `games/<chunk>/game.pkg.json` y añade:

```text
games/<chunk>/campaign/
  campaign.json
  world.json
  knowledge.json
  quests.json
  dialogues.json
  quality.json
  puzzles/<id>.json
  regions/<id>.json
```

`knowledge.json` contiene conceptos, habilidades, reglas, acciones, citas literales
con posiciones y relaciones verificadas. Se distinguen `source_fact`,
`design_inference` y `narrative_fiction`. El grafo deriva del diseño validado y
conserva trazabilidad; no demuestra por sí solo la corrección semántica del diseño.

El curso añade `campaign/game.pkg.json`, `campaign/index.html`, `campaign.json` y
`knowledge.json`. El paquete JSON incluye todos los datos de juego y se reemplaza
atómicamente después de comprobar las transiciones en Chromium. Los archivos
auxiliares se reemplazan individualmente: no hay una transacción de directorio.

La API conserva los contratos V1 y añade `POST /api/v2/generate`,
`GET /api/v2/campaigns/{course_id}` y su variante `/package`.
`/play?course={course_id}` abre la campaña; los enlaces existentes por lección
también reanudan la campaña cuando la región corresponde al paquete publicado.

## Motor, progreso y pruebas

`world/core.js` contiene WorldEngine, EventBus y SaveSystem, y árbitros puros compartidos
entre el navegador y las pruebas Node. La capa DOM/canvas está en `world/runtime.js`.
El motor emite `entity.interacted`, `npc.dialogue.completed`, `puzzle.solved`,
`puzzle.failed`, `puzzle.reset`, `world.flag.set`, `quest.started`,
`learning.observation` y `region.completed`.

El guardado está separado por curso, lección y hash del mundo, o por hash de campaña.
Una recarga conserva la región actual y no permite saltar una región previa sin
completar. Puertas, XP e inventario
se reconstruyen a partir de soluciones válidas, no de flags aisladas del guardado.
Una carga duplicada no duplica recompensas y una posición corrupta tras una puerta
cerrada se descarta. Un puzzle terminado no vuelve a producir observaciones BKT.
La telemetría conserva rutas correctas/incorrectas, congestión, pistas, tiempo,
reinicios e intentos por habilidad, además de acciones correctas/incorrectas,
pasos y tiempo en milisegundos. Los diálogos completados conservan sus flags.
Las pistas progresan desde observación del estado hasta orientación conceptual
y ayuda explícita. Las utilidades que exponen el motor solo se activan en paquetes
de prueba; la publicación normal no expone `window.worldEngine`.

Los E2E prueban una red mal conectada con teclado, fallo, pistas, reinicio, recarga
y posterior solución. Los tres arquetipos tienen regresiones de fallo y recuperación
contra el motor real. Las siete reproducciones de la revisión inicial ya son tests
obligatorios, sin `xfail`. Se corrigió además la limpieza de PDF de dos páginas y
se recuperaron contratos V1 en nuevos archivos, preservando los borrados anteriores.

OpenCode corrigió el cliente de generación: identidades de caché basadas en el hash
de la clave completa y URL normalizada; prioridad de modelo de etapa, selección
explícita y configuración global. Las pruebas usan clientes controlados sin gasto
en proveedores externos.

`pytest.ini` recoge también los tres contratos con nombres no convencionales. Se
añadió únicamente el import que faltaba en `not_exam.py`; sus condiciones se mantienen.
Los borrados preexistentes de la suite anterior se preservaron. Los tests nuevos
incluyen contratos de PDF/PPTX, API, paquetes y BKT relacionados con esta migración;
esto no equivale a recuperar toda la cobertura histórica borrada.

## Límites y siguientes fases

- Planificación espacial libre, campañas ramificadas y misiones con dependencias
  entre regiones. La campaña actual avanza por regiones en orden.
- Adaptación del siguiente puzzle a partir de BKT, narrativa contextual generada
  durante la partida y distribución de dificultad a lo largo del curso.
- Enemigos, secretos y los demás arquetipos.
- `custom_world_puzzle`: actualmente se rechaza; requiere una extensión declarativa
  y más validadores antes de habilitarse. No se permite JavaScript generado.
- Calidad visual más rica y pruebas pedagógicas con usuarios/modelos reales.

## Skills seleccionadas

Se consultó el catálogo oficial con la skill `skill-installer`. No se instalaron
skills globales: la petición era buscarlas y verificarlas. Las dependencias Python
de tests sí se instalaron en `.venv` y se declararon en requirements.

| Prioridad | Skill oficial | Aplicación |
| --- | --- | --- |
| 1 | [playwright](https://github.com/openai/skills/blob/main/skills/.curated/playwright/SKILL.md) | Recorridos de juego reales, regresiones del DOM, capturas y móvil |
| 2 | [security-best-practices](https://github.com/openai/skills/blob/main/skills/.curated/security-best-practices/SKILL.md) | Revisión del backend Python y del frontend JS que consume contenido de IA |
| 3 | [pdf](https://github.com/openai/skills/blob/main/skills/.curated/pdf/SKILL.md) | Revisar contenido y presentación del material educativo de entrada |

`playwright-interactive` es opcional para depuración visual persistente. Para esta
suite reproducible se utilizó Playwright desde Python. La skill `imagegen` no es
necesaria para este cambio: se reutilizaron el sprite y la fuente existentes.
