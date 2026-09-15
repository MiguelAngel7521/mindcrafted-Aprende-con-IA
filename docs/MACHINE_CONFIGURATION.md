# machine_configuration — World V2

**Knowledge drives the configuration.** El alumno instala componentes en ranuras
y ajusta parámetros caminando entre objetos del mundo. Las dependencias,
incompatibilidades y recursos del material determinan qué sistema puede arrancar.
El runtime implementa la mecánica una vez; las asignaturas y escenarios son datos.

## Contrato

Definición canónica: `MachineConfiguration` en `generator/world_schema.py`.
Exportación: `engine/world/machine-configuration.schema.json`, incorporada también
en los schemas de WorldSpec y CampaignSpec.

| Campo | Significado y límites |
| --- | --- |
| `archetype`, `schemaVersion` | `machine_configuration`, `1` |
| `machine` | ID y nombre del sistema; su consola es el anchor físico |
| `components` | Catálogo de 2–8 tipos de módulos con ID y etiqueta |
| `slots` | 1–4 ranuras físicas; cada una ofrece 2–4 componentes del catálogo y vacío |
| `parameters` | 1–4 selectores físicos, cada uno con 2–5 valores e `initial` explícito |
| `parameters[].values[]` | ID, etiqueta y `quantity`: entero 0–100 o `null` para valores cualitativos |
| `configurationRules` | 1–12 restricciones declarativas, todas asociadas a `ruleId` |
| `goals` | 1–8 estados requeridos; también asociados a reglas educativas |
| `tradeoffs` | Hasta cuatro preferencias opcionales: control, valores preferidos y razón |

Todos los IDs/referencias se verifican. Se rechazan IDs duplicados/reservados,
catálogos huérfanos, valores iniciales inexistentes, rangos inválidos, costes
incompletos y controles sin una restricción ejecutable. Debe existir una relación
entre controles; una colección de selectores de respuestas independientes no basta.

Las listas de componentes definen qué se puede instalar físicamente. La compatibilidad
académica se valida mediante reglas causales, por ejemplo una dependencia entre
dos ranuras. El catálogo describe tipos instalables; no añade inventario limitado
ni un sistema de consumo irreversible de piezas.

### Reglas admitidas

Una condición es `{control, values}`: el control tiene uno de esos valores.
`null` representa una ranura vacía y solo es válido en su dominio.

| Tipo | Semántica |
| --- | --- |
| `required` | Se cumple `condition` |
| `dependency` | Si se cumple `when`, debe cumplirse `then` |
| `exclusion` | `left` y `right` no pueden cumplirse simultáneamente |
| `range` | La cantidad de un parámetro está entre `min` y `max`, inclusive |
| `capacity` | La suma de los costes seleccionados no supera `max`, en la `unit` declarada |

`capacity.terms` declara un control y una tabla exhaustiva `costs: [{value, amount}]`.
Toda opción no vacía debe tener coste explícito; una ranura vacía consume cero.
Esto permite, por ejemplo, expresar tamaño de memoria y coste eléctrico como
magnitudes diferentes sin convertir el runtime en un motor de una asignatura.

Ejemplo de compatibilidad declarativa, usado en la fixture:

```json
{
  "kind": "dependency",
  "ruleId": "durability",
  "when": {"control": "mode", "values": ["online"]},
  "then": {"control": "storage", "values": ["durable"]}
}
```

Las preferencias explican compromisos entre configuraciones. Se reportan en la
prueba del solver; no cambian el éxito, la solución mínima ni las recompensas.
No pueden sustituir una regla educativa obligatoria.

## Solver y causalidad educativa

Máximo **4096 estados**, incluidas ranuras vacías. El validador rechaza espacios
mayores antes de buscar. `finite_puzzle.py` enumera las configuraciones y entrega:

- solución válida, número de soluciones y hasta tres alternativas;
- mínimo exacto de interacciones cíclicas desde el estado inicial, más activación;
- mínimo de controles distintos que deben cambiar;
- contraejemplo de ablación para cada `requiredRule`;
- tasa exacta de éxito aleatorio y 256 ensayos reproducibles con seed `20260915`.

El coste de configuración excluye caminar; el compilador calcula aparte el
recorrido transitable. Las ranuras ciclan vacío → componentes → vacío. Los
parámetros conservan el orden cíclico declarado, empezando en `initial`.

Eliminar una regla debe admitir una configuración antes inválida. Sin ese test,
se rechaza como decorativa aunque el puzzle tenga solución. También se rechazan
el estado inicial resuelto, la falta de soluciones y los límites de dificultad
incumplidos. El ratio aleatorio usa el máximo entre todos los estados y los estados
con ranuras completas: añadir ranuras vacías no puede esconder una solución trivial.

La fixture `machine_configuration_demo.py` tiene **243 estados, 3 soluciones,
9 interacciones mínimas y 5 controles que cambiar**. Las siete reglas son causales.
El ratio exacto máximo es `3/108 ≈ 2,78 %`; el muestreo da `2/256 ≈ 0,78 %`.
Es un escenario explícito de almacenamiento, confirmación y memoria, no una
afirmación universal sobre todos los sistemas de hardware o bases de datos.

## Simulación y recuperación

Python: `validate`, `initial`, `transition`, `simulate`, `solve`.
JavaScript: `machineConfiguration.initial/transition/result` en un módulo sin UI.
Los tests comparan **cada estado y cada ablación** entre ambos árbitros.

`configuration + action → new configuration` no muta el objeto de entrada.
Solo se aceptan `control`, `submit` y `reset`; acciones y estados desconocidos se
rechazan. No existen callbacks, scripts ni código de modelo ejecutable.

Fallar no destruye componentes: la configuración queda editable. Cambiar un
selector, retirar una pieza o pulsar `R` permite recuperarse. Se verifica recuperación
de los 243 estados en WorldEngine y 256 secuencias aleatorias reproducibles.
La prueba de recuperación presupone el mapa validado: el compilador exige acceso
físico a todos los controles, incluso los que una solución no utiliza.

## Integración física, estado y BKT

Una consola representa la máquina. Las ranuras muestran la pieza instalada; los
selectores muestran el valor y su posición. Cables, indicadores y presupuesto se
dibujan en el **mismo canvas**. Una incompatibilidad marca los controles afectados
y bloquea el arranque; la consola indica el fallo. El renderer consume los resultados
del árbitro y no decide éxito, quests ni recompensas.

La autoridad sigue en `WorldEngine.state.puzzles[id].configuration`. Se reutilizan
NPC, QuestSystem, DialogueSystem, FlagSystem, eventos, SaveSystem y BKT.
Una activación correcta abre la compuerta, completa la misión, pone la máquina en
marcha y cambia el diálogo del NPC. XP es una recompensa adicional.

Cada activación registra el resultado de cada regla en su habilidad BKT, junto
con intentos, acciones correctas/incorrectas, pasos, pistas, tiempo y reinicios.
Es evidencia de la configuración observada; no una afirmación de dominio basada
únicamente en `solved`. Se conservan los hints 0–4; las primeras ayudas no enumeran
todos los valores correctos.

Save/load conserva configuraciones parciales, fallos y soluciones. Restore valida
los valores y reconstruye el resultado, flags y recompensas; no confía en un
`effect.ok` almacenado. La carga no vuelve a emitir observaciones ni otorga XP
duplicada. La ampliación es compatible con saves V2 de los archetypes anteriores.

## Elegibilidad y generación

`eligibility(source)` exige al menos dos afirmaciones distintas que relacionen
componentes, modos, parámetros o estados con requisitos/compatibilidades.
Listas de palabras y repeticiones de la misma afirmación no bastan:
`SOURCE_TOO_WEAK_FOR_MACHINE_CONFIGURATION`.

La elegibilidad se comprueba antes de llamar al proveedor si se pide este archetype,
y siempre al validar su contenido. Es una heurística local, **no un Mechanic Selector**
ni un validador semántico completo. Las citas literales y sus spans se preservan
en KnowledgeGraph con bindings a `configurationRules` y `goals`.

El archetype integra BlueprintPuzzle, schemas canónicos/API, Structured Outputs,
prompts, compilador, KnowledgeGraph, reparación y QualityGate. Los tests usan
fixtures y mocks del proveedor, con validación determinista y E2E reales.
No se ha reiniciado el bake-off ni realizado llamadas a modelos externos.

## QualityGate y evidencia

El gate comprueba schema, IDs, fuentes/elegibilidad, causalidad, solver/límites,
accesibilidad, consecuencias y ejecución del runtime. El navegador verifica el
mismo mundo, configuración parcial, fallo editable, reset y persistencia. Un
juez perfecto nunca sobreescribe un fallo determinista ni una prueba no ejecutada.

Pruebas relevantes:

- `test_machine_configuration.py`: contratos, solver, ablación, elegibilidad,
  límites, generación/reparación y veto determinista.
- `test_machine_configuration_runtime.py`: 256 secuencias, recuperación de todos
  los estados, guardado y protección contra veredictos manipulados.
- `test_configuration_browser.py`: teclado real → NPC/quest → combinación
  incompatible → píxeles de fallo → corrección/reset → guardado parcial → solución
  alternativa → compuerta/NPC → reload; BKT, móvil y continuidad de engine/canvas.
- `test_pillar_campaign.py`: `node_connect + resource_balance + machine_configuration`
  en una región y otra región con ID `machine` repetido; aislamiento, eventos,
  BKT y recarga, más recorrido real del navegador entre regiones.

## Validación final

La suite completa terminó con **366 passed, 4 warnings** (50,81 s). Los cuatro
warnings existentes corresponden a `FastAPI.on_event`. `compileall`,
`node --check` en los 12 scripts World V2 y `git diff --check` pasan.
El baseline limpio era 268 tests y el cierre de resource_balance dio 298.

MACHINE_CONFIGURATION ARCHETYPE: DONE

## Revisar los tres pilares

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m mindcrafted.generator.world_tools check --archetype machine_configuration --output output/machine-configuration
.venv/bin/python -m mindcrafted.generator.world_tools check --pillars --output output/three-pillars
```

Las exportaciones son demos de desarrollo con `judge: not_run`, nunca una
aprobación IA inventada. La generación con LLM real, evaluación pedagógica y
pruebas con estudiantes continúan como **Integration Gate pendiente**.
Mechanic Selector, bosses multifase, Agent API y otros archetypes no forman parte
de esta entrega.
