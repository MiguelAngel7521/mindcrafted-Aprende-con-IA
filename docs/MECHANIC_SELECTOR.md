# V2.2 — Mechanic Eligibility & Selector

**AI MAY SUGGEST — CODE MUST VERIFY.** Baseline determinista para los tres pilares.
No utiliza modelos, aleatoriedad ni fallback a una mecánica por defecto.

## Milestone anterior

`306d485` — `feat(world-v2): complete three deterministic puzzle archetypes`.
Commit de los tres archetypes, tests, QualityGate, persistencia, BKT y E2E,
sin secretos ni archivos de entorno, sincronizado con `main` en GitHub.
Antes de continuar: **366 passed, 4 warnings**, compileall, sintaxis de los 12
JS/CJS de World V2 y `git diff --check` aprobados.

## Arquitectura y contratos

```text
Material
  → build_structure_graph (KnowledgeGraph de estructura educativa, versión 1)
  → LearningObjective + subconjunto de relaciones/conceptos
  → extract_features
  → MechanicProfile.eligibility
  → MechanicSelector.select
  → contrato allowedMechanics / eligibleMechanics / recommendedMechanic
  → PuzzleBlueprint → compilador → QualityGate → WorldEngine
```

`knowledge_features.py` implementa el grafo anterior al diseño. Su formato es
`mindcrafted-educational-structure`, versión 1, con hash SHA-256 de fuente,
conceptos expresados como extremos textuales de relaciones, predicados y evidencia
literal `start/end/quote`. Los IDs derivan del contenido.

El `KnowledgeGraph` anterior de `world_knowledge.py` sigue indexando **diseños ya
compilados**: conceptos inferidos, reglas, habilidades, citas y bindings. No se
usan sus bindings mecánicos para justificar retrospectivamente una selección.
`world_knowledge` también expone el constructor y extractor previos al diseño.

`MechanicProfile` contiene ID, señal principal, intención, mínimo de conceptos y
relaciones. Los tres módulos de archetype exponen `eligibility(source)` mediante
el mismo registro y evaluación. `world_ai_validation.source_quality` delega en
node_connect; conserva sus métricas públicas. Se reemplazaron las heurísticas
anteriores, no se mantienen tres implementaciones paralelas.

## Extracción y grounding

La gramática acotada reconoce relaciones explícitas en español e inglés:
dependencia, conexión, recepción, producción, uso, requisitos, consumo, asignación,
restricciones y compatibilidad binaria. Exige sujeto y objeto no vacíos. Después
clasifica cada relación por señales de recursos o controles; las palabras por sí
solas no crean relaciones.

Se deduplican afirmaciones por espacios/capitalización. Una lista de temas no
cuenta como relaciones. `validate_structure_graph` vuelve a extraer el grafo desde
la fuente y exige igualdad: añadir etiquetas, inventar aristas, cambiar extremos,
contadores, hash o spans produce `GROUNDING_ERROR`.

Features:

| Campo | Significado |
|---|---|
| `conceptCount` | Extremos textuales distintos en el subconjunto |
| `relationCount`, `connectionCount` | Relaciones admitidas por la gramática |
| `dependencyCount` | Predicados de dependencia/necesidad |
| `resourceCount` | Relaciones sobre recursos con asignación, consumo o límites |
| `capacityCount`, `quantityCount` | Relaciones con límites/presupuestos y cantidades |
| `quantifiedCapacityCount` | Capacidad y cantidad en **la misma evidencia** |
| `configurationCount` | Controles/modos/componentes sujetos a requisitos |
| `constraintCount`, `compatibilityCount` | Restricciones y compatibilidades |
| `componentCount`, `parameterCount` | Relaciones que involucran componentes/parámetros |
| `featureEvidence`, `relationIds` | IDs que permiten rastrear cada contribución |

Los contadores son de relaciones, no de apariciones de palabras. No se extraen
cantidades para ejecutarlas como reglas del puzzle: el Blueprint sigue requiriendo
validación, solver y prueba de causalidad educativa.

Límites: 60.000 caracteres, 512 relaciones, referencias de objetivo acotadas,
historial máximo de 100 selecciones. Se rechazan excesos antes de continuar.

## Elegibilidad

Todos requieren al menos dos relaciones relevantes distintas y tres extremos.

| Archetype | Condición adicional |
|---|---|
| `node_connect` | Relaciones explícitas admitidas por la gramática |
| `resource_balance` | Dos relaciones de recursos y al menos una capacidad cuantificada |
| `machine_configuration` | Dos relaciones de configuración y dependencia o compatibilidad |

La respuesta común incluye `eligible`, `status`, `score`, `reasons`,
`relationshipCount` y los `evidenceRelationIds` que sustentan la señal.
Se conservan `SOURCE_TOO_WEAK_FOR_NODE_CONNECT`,
`SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE` y
`SOURCE_TOO_WEAK_FOR_MACHINE_CONFIGURATION`.

## Scoring y ambigüedad

Sea `n` el número de relaciones del objetivo, `r` las de recursos y `c` las de
configuración. Para candidatos elegibles:

- Node: `0.55 + 0.25 × (1 − min(n, r+c)/n) + 0.10 × min(n/6, 1)`.
- Resource: `0.65 + 0.20 × r/n + 0.05 × I(capacity) + 0.05 × I(quantity)`.
- Machine: `0.65 + 0.20 × c/n + 0.05 × I(dependency) + 0.05 × I(parameter)`.
- Intención explícita correspondiente: `+0.04`. `I` vale uno si existe la feature.

Score limitado a `[0,1]`, redondeado a cuatro decimales; los no elegibles reciben
cero. Son puntuaciones de ranking, **no probabilidades calibradas**.
Las razones incluyen los conteos, umbrales e intención aplicada.

Se selecciona el único elegible o el primero cuando supera al segundo por **más
de 0.05**. En otro caso: `AMBIGUOUS_MECHANIC_SELECTION`, candidatos conservados,
selección y recomendación nulas. Sin candidatos: `NO_ELIGIBLE_MECHANIC`.
Ordenar nombres estabiliza el informe, nunca resuelve por sí solo un empate.

Diversidad solo puede romper un empate **exacto** de score, después de dos
repeticiones consecutivas, si queda una única alternativa igual de adecuada.
Nunca elige un score menor para variar. Un margen de 0.04 sigue siendo ambiguo.

## LearningObjective y modos

`LearningObjective(id, text, relation_ids=None, concept_ids=None, intent='explore')`.

- `relation_ids` limita las relaciones; una tupla vacía produce alcance vacío.
- `concept_ids` crea un subgrafo inducido: ambos extremos deben estar incluidos.
- Si se indican ambos filtros, se aplica su intersección; referencias desconocidas
  fallan. Sin filtros, se analiza toda la fuente.
- `intent`: `explore`, `connect`, `distribute` o `configure`. No infiere intención
  con keywords del texto libre. El texto explica el objetivo; el alcance determina
  su evidencia. Cambiar el título no incorpora relaciones de otra sección.

```python
from mindcrafted.generator.world_knowledge import build_structure_graph, LearningObjective
from mindcrafted.generator.mechanic_selector import MechanicSelector

graph = build_structure_graph(source)
objective = LearningObjective('topology', 'Reconstruir la topología',
                              relation_ids=tuple(topology_relation_ids), intent='connect')
result = MechanicSelector().select(graph, source, objective, mode='AUTO')
```

`AUTO` no fuerza selección. Un ID de archetype fuerza authoring compatible; si no
es elegible, se lanza `INELIGIBLE_FORCED_MECHANIC`. Este override puede preferir
una mecánica elegible de score menor, y queda explicado en el resultado.

`generate_campaign(..., archetype='AUTO', learning_objective=objective)` analiza
antes de cualquier llamada. Ningún candidato o ambigüedad detienen la generación.
Los archetypes forzados también se verifican antes del proveedor.
El valor histórico `archetype=None` conserva el authoring legacy, explícitamente
marcado `legacyAuthoring`; no se ha cambiado silenciosamente a AUTO.

## Generación y QualityGate

El contrato aporta `eligibleMechanics`, `recommendedMechanic`, `allowedMechanics`
y, para AUTO/forzado, `learningObjective` y el informe `mechanicSelection`.
AUTO fija el schema al recomendado; el authoring legacy restringe el schema a sus
mecánicas históricas y pilares elegibles. `blueprint_response_schema` permite
restringir un conjunto de archetypes; también funciona con Structured Outputs.

No hay AI Planner ni nuevas llamadas de selección. Las llamadas existentes de
**diseño y juez** se prueban mediante mocks. Una futura sugerencia IA deberá
pertenecer al conjunto verificado. `generation_contract` no inventa recomendación
cuando el resultado es ambiguo.

Con un objetivo explícito, `verify_objective_binding` rechaza reglas cuya evidencia
no pertenezca a sus relaciones (`OBJECTIVE_SCOPE_ERROR`). Sin objetivo explícito,
el QualityGate igualmente limita la evaluación a las citas del puzzle. El fallback
solo puede reutilizar un paquete aprobado de la misma fuente que además respete
la mecánica seleccionada y el objetivo explícito; se vuelve a ejecutar su gate.
Un candidato de otro objetivo no se publica como recuperación silenciosa.

`validate_mechanics`, `validate_world` y `quality_gate` rechazan pilares no elegibles.
El informe incluye `checks.mechanicEligibility` y el detalle por puzzle; es una
condición de publicación y composición de campañas. Un juez perfecto no supera
este fallo. Los tres archetypes históricos tienen estado `LEGACY_COMPATIBILITY`;
no son candidatos del selector ni se presentan como estructuralmente verificados.

## Tres objetivos y E2E

`selector_demo.selected_blueprint()` construye un solo grafo a partir del material
combinado; cada objetivo cita su subconjunto. Ejecuta la selección antes de buscar
la fixture correspondiente en el catálogo de demostración:

| Objetivo | Resultado |
|---|---|
| Dependencias por capas | `node_connect` |
| Asignación por latencia y capacidad | `resource_balance` |
| Configuración de almacenamiento y memoria | `machine_configuration` |

No es un Campaign Planner general. La prueba integrada compila estos tres puzzles,
ejecuta el QualityGate real, compone otra región con IDs de puzzle repetidos y
recorre la campaña en Chromium. Usa los probes existentes de teclado, fallo,
recuperación, guardado parcial/resuelto, recompensas, BKT y continuidad de canvas.
Las pruebas anteriores de campaña conservan las comprobaciones de aislamiento,
transiciones y ausencia de eventos/observaciones duplicadas.

```sh
.venv/bin/python -m mindcrafted.generator.world_tools check --selector-demo --output output/mechanic-selector
```

Genera `mechanic-selection.json`, `validation.json`, `world.json` e `index.html`.
La demo sigue con `judge: not_run`; pasar pruebas deterministas no fabrica
aprobación IA para publicación.

## Material académico real

No había un corpus académico de estudiante versionado. Se conservaron fragmentos
literales públicos con ubicación/URL en
`tests/fixtures/mechanic_selector/academic_excerpts.json`, y resultados completos
reproducibles en `academic_results.json`.

| Fuente y alcance | Relaciones | Resultado |
|---|---:|---|
| [OpenDSA, Graph Traversals](https://opendsa.cs.vt.edu/ODSA/Books/CS3S26masterslides/html/Graphs.html), dos fragmentos | 2 | node_connect, 0.8333 |
| [ThinkCS, Dictionaries](https://www.openbookproject.net/thinkcs/python/english3e/dictionaries.html), un párrafo | 1 | NO_ELIGIBLE_MECHANIC |
| [OSTEP, Address Spaces](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf), una oración | 1 | NO_ELIGIBLE_MECHANIC |
| Mismo capítulo OSTEP **completo**, nueve páginas | 21 | node_connect, 0.9 |

Para el capítulo completo, se usó literalmente la salida de `pdftotext -layout`,
sin editar el material ni etiquetarlo para favorecer una mecánica. Hay 41 extremos,
3 dependencias, 1 relación con cantidad y ninguna capacidad cuantificada reconocida.
El informe [MECHANIC_SELECTOR_OSTEP.json](evidence/MECHANIC_SELECTOR_OSTEP.json)
conserva URL, hash del PDF, hash/longitud del texto, versión del extractor, features,
candidatos, scores y explicación; no redistribuye el capítulo.

La extracción inicial con pypdf emitió avisos de fuentes CFF por ausencia de
`fontTools` opcional. Se usó el `pdftotext` existente para el resultado definitivo;
no se añadió una dependencia. Los fragmentos offline no requieren PDF, red ni OCR.

Reproducción del análisis completo:

```sh
curl --fail --silent --show-error https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf -o /tmp/ostep.pdf
pdftotext -layout /tmp/ostep.pdf /tmp/ostep.txt
.venv/bin/python -m mindcrafted.generator.mechanic_tools /tmp/ostep.txt --objective 'Understand address space virtualization' --objective-id memory --output /tmp/selection.json
```

El CLI sirve también para cualquier material UTF-8 local. Permite filtrar por
`--relation ID` y `--intent`; exporta IDs, conteos y hash, sin texto de estudiante.

## Límites y validación

- La gramática no comprende todo el lenguaje natural. Saltos de línea, expresiones
  implícitas, negaciones complejas, fórmulas, tablas, sinónimos o correferencias
  pueden producir omisiones o extremos poco precisos. No resuelve equivalencia
  semántica entre conceptos expresados de formas distintas.
- Una cita literal demuestra procedencia, no verdad académica ni calidad del puzzle.
  La admisión de relaciones genéricas puede dar falsos positivos para node_connect.
  Eligibility no sustituye causalidad educativa, solver, E2E o revisión pedagógica.
- No se calibraron scores contra un corpus amplio ni estudiantes. Los ejemplos
  reales anteriores no certifican cobertura de un curso ni todos los dominios.
- El parser y los perfiles actuales son deterministas y conservadores para recursos
  y configuración; es correcto no escogerlos aunque el documento trate esos temas.
- Se preserva el authoring legacy y se habilita AUTO explícito. No hay cambio global
  de producto ni selección por IA, bosses, nuevos archetypes o NPC dinámicos.

Tests: extracción/grounding, contrato común, scoring, ningún elegible, ambigüedad,
objetivos y scope, diversidad subordinada al ajuste educativo, fuente alterada,
100 permutaciones reproducibles, material real, schemas/prompts, veto de QualityGate,
generación AUTO con mocks y E2E real, y campaña mixta seleccionada.

### Resultado de cierre

- **415 tests PASS** (49 añadidos sobre el baseline de 366), 61,85 s.
- Cuatro `DeprecationWarning` conocidos de FastAPI `on_event` en `server.py`;
  no hubo fallos ni skips en la suite completa.
- `python -m compileall mindcrafted`: PASS.
- `node --check`: PASS para los 12 JS/CJS de World V2; esta fase no cambia JS.
- `git diff --check`: PASS.
- Demo seleccionada: siete checks deterministas PASS, E2E/recovery/reload PASS,
  `judge: not_run` y `approved: false` como corresponde a una fixture de desarrollo.
- Reproducción del análisis completo de OSTEP contra su informe guardado: PASS.

MECHANIC SELECTOR: DONE
