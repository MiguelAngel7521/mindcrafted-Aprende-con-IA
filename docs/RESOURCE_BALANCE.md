# resource_balance — World V2

El jugador camina entre cargas indivisibles y receptores. `E` en una carga cambia
su receptor; un ciclo completo la retira. La consola activa el reparto. La
compatibilidad conceptual y la suma de consumo determinan el resultado. El motor
no conoce asignaturas; el ejemplo de scheduling es contenido declarativo.

## Contrato y límites

`ResourceBalance` en `world_schema.py` y `resource-balance.schema.json`:

- `schemaVersion: 1`, `archetype: resource_balance`.
- `loads`: 2–6 cargas con `id`, `label`, `kind`, `amount` entero positivo.
- `targets`: 2–4 receptores con `id`, `label`, `kind`.
- `allocationRules`: compatibilidad de `sourceKind/targetKind` y capacidad
  agregada con `limits: [{target, min, max}]`.
- `goals`: `all_assigned`.
- Toda regla/meta referencia `knowledge.requiredRules` mediante `ruleId`;
  las citas se verifican literalmente y se indexan en KnowledgeGraph.
- Máximo nueve objetos y 4096 estados, incluyendo cargas sin asignar.
- IDs únicos/no reservados, referencias verificadas, ningún código ejecutable.

La elegibilidad local requiere al menos dos afirmaciones distintas sobre cargas,
asignación y capacidad. Una lista de palabras no basta:
`SOURCE_TOO_WEAK_FOR_RESOURCE_BALANCE`. Es una heurística, no validación semántica.

## Solver, simulación y causalidad

`resource_balance.py` implementa `validate`, `initial`, `transition`, `simulate`
y `solve`; `resource-balance.js` aplica el mismo contrato sin renderer.
El helper `finite_puzzle.py` enumera los estados acotados y entrega solución,
alternativas, mínimo de interacciones cíclicas más activación y mínimo de controles
distintos que cambiar. No incluye desplazamiento en el coste de configuración.

Cada regla debe tener un contraejemplo: al quitarla se admite una configuración
que antes fallaba. Reglas decorativas, estados iniciales resueltos, falta de
solución o exceso de éxito aleatorio rechazan el candidato. Se calcula el máximo
del ratio global y del ratio de asignaciones completas, para no ocultar soluciones
triviales tras cargas vacías. Además se simulan 256 configuraciones con seed fija.

La fixture tiene 256 estados, dos soluciones, ocho interacciones y éxito aleatorio
máximo `2/81 ≈ 2,47 %`. Las tres reglas —latencia, capacidad, disponibilidad— son
causales. Los tests comparan todos los estados y ablaciones entre Python y JS,
y ejecutan 256 secuencias aleatorias con recuperación y recarga en WorldEngine.

## Integración, persistencia y QualityGate

`WorldEngine.state.puzzles[id].configuration` contiene las asignaciones. Los cables,
unidades de carga, medidores e indicadores se dibujan en el canvas principal.
Una activación incorrecta conserva el reparto editable, muestra el fallo y registra
evidencia por regla; `R` restaura el estado inicial. Se reutilizan los hints 0–4,
NPC, quests, eventos, flags, SaveSystem y BKT existentes.

Resolver abre una compuerta, restaura indicadores, completa la quest y cambia el
diálogo del NPC. Restore valida las asignaciones y vuelve a calcular éxito y
consecuencias; datos corruptos no otorgan recompensas. La recarga no emite nuevas
observaciones ni duplica XP/inventario.

El QualityGate verifica contratos, fuentes, solver, causalidad, controles físicos
accesibles, recorrido del runtime y navegador. El E2E realiza asignación parcial,
recarga, fallo, recarga, pista, reset, solución y consecuencia. El recorrido de
`test_configuration_browser.py` comprueba píxeles, teclado, reacción de NPC y BKT.
Los contratos de generación usan un modelo mock con reparación y QualityGate real.
Un juez perfecto no puede aprobar un fallo determinista.

## Verificar

```sh
.venv/bin/python -m pytest -q tests/test_resource_balance.py tests/test_configuration_browser.py
.venv/bin/python -m mindcrafted.generator.world_tools check --archetype resource_balance --output output/resource-balance
```

El contrato de generación y el archetype están implementados. La generación con
LLM real y su juicio pedagógico siguen como **Integration Gate pendiente**; la
fixture de desarrollo no representa una campaña aprobada por IA.

RESOURCE_BALANCE ARCHETYPE: DONE
