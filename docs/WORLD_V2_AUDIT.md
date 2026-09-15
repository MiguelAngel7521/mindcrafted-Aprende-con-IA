# Auditoría de arquitectura — 13–14 de septiembre de 2026

Contrato leído completo: `AGENTS.md` y `MINDCRAFTED_V2_ASTRA.md` de la raíz.
Al iniciar esta auditoría había cambios en curso en el motor World V2 y su exportador,
además de los documentos actualizados por el usuario. Se conservaron. La suite previa
a nuevos cambios de este bloque dio **155 passed, 4 warnings**, en 81,77 s.
Es una medición del árbol de trabajo, no del commit limpio anterior.

## Estructura y dependencias

| Área | Clasificación | Implementación y consumidores |
| --- | --- | --- |
| Entrada y cursos | Compartida | `mindcrafted/server.py`, `generator/course_pipeline.py`, `course_assembler.py`, `static/studio.html`. Studio solicita `gameplay: world`; `/play` selecciona reproductor por paquete. |
| Proveedor IA | Compartida | `generator/api.py`: cliente compatible con OpenAI, URL/clave/modelo configurables y modelo por etapa. No envía `response_format` ni tools actualmente. |
| Dispatch de generación | Compartida | `generator/pipeline.py::generate_game`: World V2 por defecto con `fast_mode`, `adventure` y `world_native`; ramas explícitas legacy permanecen. Parser y configuración se reutilizan. |
| Pipeline canónico | V2 | `world_pipeline.py`: Blueprint, compilación, pruebas, juez, reparación hasta tres candidatos; fallback únicamente previamente aprobado para la misma fuente. |
| Contratos y compilación | V2 | `world_schema.py`, schemas JSON exportados y `world.py`: tres arquetipos, una región por WorldSpec, entidades físicas, quests y diálogos compilados. |
| Solución y simulación | V2 | `world_solver.py`, `world/probe.cjs`, `world_package.py`: búsqueda acotada, recorrido espacial y reproducción en motor real. |
| Conocimiento | V2 | `world_knowledge.py`: citas con offsets y vínculos regla→mecánica. El grafo se deriva del diseño; todavía no es un extractor independiente anterior al planner. |
| Paquete y publicación | V2 | `world_package.py`: todos los checks obligatorios y juez; revalidación al escribir. `world_campaign.py`: composición de regiones y hashes. |
| Motor | V2 | `engine/world/core.js`, `runtime.js`, `player.html`, `campaign.js`: jugador, canvas, colisión, puzzle, puertas, guardado por mundo/campaña. |
| Eventos y narrativa | V2 | Extracción en curso a `event-bus.js`, `flag-system.js`, `quest-system.js`, `dialogue-system.js`, conservando las interfaces de WorldEngine. |
| BKT | Compartida | `engine/bkt.js`: por curso/habilidad; World V2 suministra observaciones por regla, intentos, errores, pistas, congestión y tiempo. |
| Aventura con encuentros | Legacy | `generator/adventure.py`, `adventure_rules.py`, `boss.py`, `engine/adventure/*`: mapas y movimiento, pero `openMission → startEncounter → arena → resumeWorld`. Sigue atendiendo paquetes antiguos. |
| Práctica y minijuegos clásicos | Legacy | `practice.py`, `fast_template.py`, `engine/practice/*`, `engine/engine.js`, `engine/player.html`, `engine/template.html`, `engine/minigames/*`. |
| Generación de código | Legacy | Ramas de simulaciones/pixel art en `pipeline.py` y `prompts.py`; `assembler.py`, `package_builder.py`, `sandbox.py`, `sandbox_harness.js`. Importados por infraestructura compartida, no cargados como gameplay World V2. |
| Material y arte | Compartida | Importadores PDF/PPTX; `assets/`; `pixel_worlds/` contiene fuentes Aseprite/Tiled, exportadores y visor. World V2 reutiliza sprite/fuente; sus layouts actuales los compila `world.py`. |
| Validación | Compartida/V2 | `tests/`, `pytest.ini`, `requirements-dev.txt`: Node, pytest, ASGI y Playwright/Chromium. `docs/` documenta V2; documentación histórica de raíz describe V1. |

## Búsqueda de UI legacy

- `launchMiniGame` y `#mini-game-overlay`: motor clásico, plantillas y parche de
  compatibilidad en `course_pipeline.py`. Los paquetes antiguos todavía los consumen.
- HTML/JS generado e inyección de scripts: reproductor clásico y ensamblador legacy.
- Canvas adicionales: títulos, partículas y simulaciones legacy, además de portadas
  del catálogo. No todos son juegos obligatorios; no corresponde eliminarlos globalmente.
- Aventura legacy reutiliza su canvas para una arena: contar canvas al terminar
  **no basta** para demostrar continuidad del mundo.
- World V2 carga únicamente BKT y scripts `engine/world/`; la exportación embebe
  runtime escrito en el repositorio y datos JSON escapados. No carga encounters,
  `launchMiniGame`, iframe ni HTML de puzzle del modelo.

No se eliminó legacy ni se modificaron sus tests existentes.

## Cumplimiento y brechas encontradas

| Requisito | Estado comprobado al auditar |
| --- | --- |
| `AI DESIGNS — CODE DECIDES` en V2 | Implementado: schemas estrictos, referencias, reglas deterministas; diálogo no puede establecer flags de compuertas educativas. |
| Puzzles físicos obligatorios | Implementado para `route_network`, `switch_sequence`, `push_blocks`: `runtime=world`, anchor, controles físicos y puerta. |
| Solución, acceso, recuperación | Solvers acotados, BFS espacial y reproducción del recorrido; tests de errores/reset para los tres arquetipos. No equivale a explorar todos los estados posibles de cada campaña. |
| Consecuencias, NPC, quests, guardado | Implementados; extracción de sistemas en curso. El feedback gráfico de red fallida perdía sus cables por el reset; el feedback no se reconstruía al cargar. |
| E2E y separación legacy | Navegador real, teclado, recarga y móvil. Brecha: comprobación de overlays al final y ausencia de una prueba completa de reacción del NPC y continuidad durante cada acción. |
| Autoridad del juez | Checks obligatorios antes del juez y al publicar; tests de rechazo con juez perfecto y checks ausentes/fallidos. |
| Acoplamiento educativo | Cada regla debe cambiar soluciones al eliminarla; citas verificadas. La corrección semántica sigue dependiendo de revisión educativa/juez, no queda demostrada por esa ablación. |
| Dificultad aleatoria | Ratio exacto de configuraciones completas válidas; falta cobertura de estrategias aleatorias de interacción con seeds. No es una medida universal de dificultad. |
| Pistas y spoilers | Introducción sin solución solicitada por prompt; ayudas progresivas existentes, pero tres niveles efectivos y sin detector general de spoilers. |
| `node_connect`, `resource_balance`, `machine_configuration` | Pendientes en schema, runtime, solver, generación y pruebas. No declararlos implementados. |
| Boss multifase | Pendiente. El actual `role=boss` reutiliza un arquetipo y combina habilidades previas; no cumple aún el contrato multifase de 2–4 mecánicas. El boss legacy no satisface V2. |
| Agent API / Structured Outputs | Pendientes. Hay pipeline restringido y schema local, pero llamadas de texto, sin JSON Schema en el protocolo ni tool calling. |
| NPC dinámicos, BKT adaptativo | Pendientes; no hay llamadas IA por frame. |
| Diversidad estadística | Pendiente. Layouts repetibles y pruebas de fixtures no prueban diversidad de generaciones reales. |
| Repair y diagnósticos | Tres candidatos y errores incluidos; faltan taxonomía estable, trazas completas y reparación localizada garantizada. El fallback descarta algunos errores sin conservar su causa. |

## Bloque seleccionado

Consolidar y verificar el recorrido físico de `route_network` antes de añadir arquetipos:
NPC → quest → cableado → congestión → reset → solución → energía/puerta → reacción
del NPC → guardado/recarga. Conservar el feedback y extraer los sistemas existentes.
Agregar detección de encuentros incluso transitorios al E2E del QualityGate y pruebas
negativas del detector; verificar píxeles del mapa para detectar otra escena en el mismo canvas.

No se utiliza un proveedor pagado para esta validación; los tests de generación usan
respuestas controladas. No se afirma aprobación de un juez real ni finalización de V2.

## Resultado del bloque

- Feedback físico de red corregido: cableado del envío fallido, congestión, cargas,
  luces de consola y recuperación. El feedback se reconstruye al recargar.
- Sistemas extraídos e integrados con eventos locales por mundo; el bus de campaña
  no activa sistemas de otras regiones. Restore no repite recompensas ni observaciones.
- Pistas 0–4 diferenciadas para los tres arquetipos existentes. La nueva prueba
  detectó primero el nivel 0 incorrecto; se corrigió antes de la validación final.
- E2E físico completo y cinco regresiones negativas del detector de continuidad.
- 256 configuraciones de red, seed `20260913`: 13 válidas (5,078 %). Todas coinciden
  con el árbitro Python; los fallos se reinician, resuelven y guardan/cargan en JS.
  Esto amplía la cobertura aleatoria, sin probar diversidad generativa ni todas las
  políticas de interacción posibles.

Archivos del bloque:

```text
mindcrafted/engine/world/core.js
mindcrafted/engine/world/event-bus.js
mindcrafted/engine/world/flag-system.js
mindcrafted/engine/world/quest-system.js
mindcrafted/engine/world/dialogue-system.js
mindcrafted/engine/world/runtime.js
mindcrafted/engine/world/player.html
mindcrafted/generator/world_package.py
mindcrafted/generator/world_continuity.py
tests/test_world_native_routing.py
tests/test_world_systems.py
docs/WORLD_V2.md
docs/WORLD_V2_AUDIT.md
```

Validación final:

| Comprobación | Resultado |
| --- | --- |
| Suite anterior, antes de continuar | 155 passed, 4 warnings |
| E2E nuevo, incluyendo detector negativo | 6 passed |
| Sistemas, navegador y campañas seleccionados | 27 passed |
| Suite completa final: `.venv/bin/python -m pytest -q` | **168 passed, 4 warnings, 77,29 s** |
| `compileall` en `mindcrafted` y `tests` | PASS |
| `node --check` en motor legacy, BKT y todos los scripts World V2 | PASS |
| `git diff --check` | PASS |
| Modificaciones/borrados de tests preexistentes | Ninguno |

Las cuatro advertencias son de `FastAPI.on_event`, ya presentes en la base.
Los contratos de raíz editados por el usuario se conservaron sin modificarlos.
La demo de desarrollo está en `output/world-native-routing/index.html`, con capturas
del fallo y la red restaurada. No es una publicación aprobada por un juez IA.

Se intentó enviar una revisión independiente a OpenCode y escribir la nota de canvas.
Nodeterm respondió `Agent messaging refused` y `Sticky write refused`, respectivamente,
incluso con acceso local autorizado fuera del sandbox. No se entregó esa delegación
ni se creó la nota; el resultado anterior corresponde a verificación local.

Siguiente bloque recomendado: contrato de `node_connect` y un slice con schema,
compilador, solver, simulación, recuperación, persistencia, acoplamiento educativo,
generación y QualityGate/E2E. Los bosses multifase y Agent API siguen después de
consolidar los tres arquetipos prioritarios. No se adelantaron esas fases aquí.
