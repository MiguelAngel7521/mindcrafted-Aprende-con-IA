# Auditoría independiente para la migración MindCrafted 2.0

Actualizada: 9 de septiembre de 2026.
Este archivo es documentación Markdown con extensión .mk. No es un Makefile.
Auditoría realizada sobre el worktree compartido para coordinar el trabajo de
Codex con la implementación de WorldSpec, WorldEngine y la vertical slice.

## 1. Resultado ejecutivo

La nueva batería de contratos expresa la dirección correcta, pero todavía no
puede ejecutarse de forma válida. `pytest` encuentra seis tests y los seis fallan
porque falta el fixture `world_spec`. Tres contratos adicionales están escritos
en archivos con guion, por lo que no entran en el descubrimiento normal de
pytest. `tests/not_exam.py` tampoco puede importarse porque usa `pytest` sin
`import pytest`.

La regresión más seria es que 13 archivos de la suite anterior aparecen borrados
en el worktree: pruebas Python, fixtures y recorridos Chromium. La migración debe
conservarlos o portar sus contratos antes de considerarse completa.

## 2. Inventario de tests actual

Tests de contrato nuevos:

- `tests/test_world_generation_contract.py`: seis funciones pytest sobre jugador,
  runtime world, anchors, ausencia de overlay, diálogos y aprendizaje.
- `tests/anti-softlock.py`: exige reset o auto-reset para puzzles obligatorios.
- `tests/puzzle-in-the-world.py`: exige una consecuencia observable al completar.
- `tests/not_exam.py`: evita cuatro arquetipos de quiz en puzzles obligatorios.

Archivos de la suite anterior borrados del worktree y presentes en `HEAD`:

- `tests/test_adventure.py`
- `tests/test_bkt.py`
- `tests/test_course_assembler.py`
- `tests/test_fast_pipeline.py`
- `tests/test_pdf_import.py`
- `tests/test_pptx_import.py`
- `tests/check_adventure_browser.mjs`
- `tests/check_adventure_models.cjs`
- `tests/check_practice_browser.mjs`
- `tests/create_adventure_upload.py`
- `tests/create_practice_upload.py`
- `tests/serve_practice_fixture.py`
- `tests/practice_fixtures.py`

No existe actualmente `tests/conftest.py`, `pytest.ini`, `pyproject.toml` ni
`setup.cfg` para declarar el fixture o cambiar el patrón de descubrimiento.

## 3. Baseline ejecutado

Comandos:

    .venv/bin/python -m pytest -q
    .venv/bin/python -m pytest --collect-only -q
    .venv/bin/python -m pytest -q tests/anti-softlock.py
    .venv/bin/python -m pytest -q tests/puzzle-in-the-world.py
    .venv/bin/python -m pytest -q tests/not_exam.py
    .venv/bin/python -m unittest discover -s tests -p 'test*.py' -v

Resultados:

- `pytest -q`: 6 errores de setup por fixture `world_spec` inexistente.
- `pytest --collect-only -q`: 6 tests recogidos; los tres archivos con guion no
  aparecen en el descubrimiento predeterminado.
- `anti-softlock.py`: 1 error de setup por `world_spec` inexistente.
- `puzzle-in-the-world.py`: 1 error de setup por `world_spec` inexistente.
- `not_exam.py`: error de colección, `NameError: pytest is not defined`.
- `unittest discover`: 0 tests ejecutados; los contratos nuevos son funciones
  pytest y la suite anterior está ausente del worktree.

## 4. Hallazgos de contrato

### Alta prioridad

- Falta un fixture `world_spec` determinista. Debe cargar una fixture mínima de
  campaña y permitir parametrizar casos válidos, softlock y referencias inválidas.
- La suite de regresión anterior no debe desaparecer. Su borrado elimina cobertura
  de importación PDF/PPTX, BKT, pipeline, empaquetado, modelos y navegador.
- Los contratos con guion deben renombrarse a módulos recogibles, por ejemplo
  `test_anti_softlock.py`, `test_puzzle_in_the_world.py` y `test_not_exam.py`, o
  incluirse explícitamente mediante configuración y ejecutarse en CI.
- `tests/not_exam.py` necesita importar pytest antes del decorador.

### Prioridad media

- `test_world_generation_contract.py` no comprueba que `spawnRegion` exista en
  `regions`, que los IDs de entidades sean únicos ni que una región tenga mapa.
- `all_entities()` sobrescribe silenciosamente entidades con IDs duplicados.
- Los anchors solo se comprueban como strings presentes; no se valida que sean
  interactuables ni que estén en una posición caminable.
- Las referencias de diálogo solo cubren `success.dialogue`; faltan triggers,
  `onComplete`, efectos y entidades referenciadas por sus IDs.
- La comprobación de ausencia de overlay serializa el JSON, pero no inspecciona el
  runtime empaquetado ni garantiza que el puzzle se resuelva dentro del mapa.
- `anti-softlock.py` comprueba la existencia de reset, pero no ejecuta un fallo y
  verifica que flags, inventario, puerta y misión vuelvan a un estado jugable.
- `puzzle-in-the-world.py` comprueba que exista algún efecto, pero no que el efecto
  apunte a una entidad o región válida ni que sea observable después de resolver.
- `not_exam.py` solo evita cuatro nombres de arquetipo en puzzles obligatorios;
  no exige por sí mismo `runtime == "world"` ni una interacción no trivial.
- Todavía no hay contratos para schema, solver determinista, ruta entre regiones,
  condición de salida, límite de intentos ni precedencia de los tests sobre un
  posible AI Judge.

## 5. Tests que deben conservarse en la migración

- Importar PDF y PPTX, rechazar formatos, firmas y tamaños inválidos.
- Validar planes, evidencia literal, soluciones numéricas, duplicados y mecánicas.
- Verificar BKT, persistencia y separación entre desempeño educativo y reflejos.
- Verificar rutas de aventura, colisiones, estaciones, portal, jefe y guardado.
- Verificar que el HTML exportado sea autocontenido y no ejecute código generado
  arbitrariamente por la IA.
- Recorrer la UI en Chromium en escritorio y móvil con fixtures sin llamadas de IA.
- Mantener casos de contenido parcial, lecciones fallidas y navegación no contigua.

## 6. Skills revisadas

El catálogo curado de Codex se consultó con:

    python3 /home/jorge75/.codex/skills/.system/skill-installer/scripts/list-skills.py --format json

Recomendación para esta fase:

| Skill | Decisión | Motivo | Instalación |
| --- | --- | --- | --- |
| `playwright` | Instalar primero | Automatización real de Chromium desde terminal | `python3 /home/jorge75/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/playwright` |
| `security-best-practices` | Instalar primero | Revisión de FastAPI/Python y frontend JavaScript | `python3 /home/jorge75/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/security-best-practices` |
| `security-threat-model` | Instalar después | Amenazas sobre uploads, paquetes, IA y ejecución en navegador | `python3 /home/jorge75/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/security-threat-model` |
| `pdf` | Instalar primero | Revisión visual y textual del flujo PDF | `python3 /home/jorge75/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/pdf` |
| `playwright-interactive` | Opcional | Depuración persistente de UI local; requiere `js_repl` y configuración especial | `python3 /home/jorge75/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/playwright-interactive` |

Las skills públicas complementarias ya investigadas son `test-driven-development`,
`systematic-debugging`, `verification-before-completion`, `webapp-testing`,
`domain-modeling` y `frontend-design`. No se instalaron automáticamente.

## 7. Orden recomendado para Codex

1. Añadir `world_spec` y hacer que los cuatro archivos de contrato se descubran.
2. Restaurar o portar los 13 tests borrados antes de retirar cualquier contrato.
3. Implementar schema, referencias, solver y validación de rutas antes del AI Judge.
4. Añadir casos negativos de softlock, reset, salida bloqueada y entidad ausente.
5. Ejecutar pytest, unittest, validadores de assets y Chromium con fixtures.
6. Usar el resultado determinista como condición obligatoria para publicar el
   World Package.

## 8. Comunicación

El intento de enviar este informe directamente a la otra terminal fue rechazado
por Nodeterm con `Agent messaging refused`, y la escritura en la nota compartida
también fue rechazada. Este archivo queda como canal de coordinación disponible
en el worktree compartido para que Codex pueda leer los hallazgos.

## 9. Fuentes de skills

- https://skills.sh/openai/skills/playwright
- https://skills.sh/openai/skills/playwright-interactive
- https://skills.sh/openai/skills/security-best-practices
- https://skills.sh/openai/skills/security-threat-model
- https://skills.sh/openai/skills/pdf
- https://skills.sh/anthropics/skills/webapp-testing
- https://opencode.ai/docs/skills/
