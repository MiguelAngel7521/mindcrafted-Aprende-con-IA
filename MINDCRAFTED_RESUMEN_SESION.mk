# Resumen de sesión y skills recomendadas para MindCrafted

Actualizada: 9 de septiembre de 2026.
Este archivo es documentación en Markdown con extensión .mk. No es un Makefile y
no debe ejecutarse con make.

## 1. Objetivo de la sesión

Convertir MindCrafted en una plataforma donde el estudiante sube apuntes en PDF,
PPTX o Markdown, revisa las lecciones extraídas y practica el contenido dentro
de mundos pixel art. Además de la práctica tradicional, se implementó un modo de
aventura con exploración, estaciones, encuentros de acción y jefe final.

## 2. Qué existe ahora

### Flujo de contenido

    PDF/PPTX/Markdown
      -> importación y revisión en el estudio
      -> generación por lección
      -> plan JSON educativo validado localmente
      -> mundo pixel art integrado en el paquete
      -> reproductor de práctica o aventura

- `mindcrafted/pdf_import.py` extrae texto de PDF dentro de límites de tamaño y
  páginas.
- `mindcrafted/pptx_import.py` extrae texto de presentaciones `.pptx`.
- `mindcrafted/server.py` expone importación, análisis, generación, cursos y
  reproducción de paquetes.
- `mindcrafted/generator/course_pipeline.py` recorre las lecciones, conserva el
  orden de las que se generaron correctamente y prepara el cierre del curso.
- `requirements.txt` declara las dependencias de FastAPI, proveedor de IA,
  importadores PDF/PPTX y utilidades del servidor.

### Generación educativa

- `mindcrafted/generator/practice.py` genera entre 3 y 5 puzzles por lección.
- La IA devuelve datos y narrativa; el código local valida estructura, evidencia,
  rangos, soluciones, mecánicas admitidas y duplicados.
- Se admiten ocho mecánicas: ecuaciones, fracciones, circuitos, relaciones de
  conceptos, orden de procesos, elección con evidencia, rutas de paquetes y
  seguimiento de algoritmos.
- Las respuestas numéricas, rutas y estados de algoritmos se calculan o validan
  localmente, no mediante JavaScript generado por la IA.
- La selección del mundo se separa de la mecánica. Los temas de programación,
  redes, datos e informática pueden usar `technology` aunque también trabajen
  con números.
- Se mantiene una reparación acotada de un plan inválido; no se sustituyen
  lecciones sin fundamento por preguntas genéricas.

### Modo aventura

- `mindcrafted/generator/adventure.py` convierte un paquete de práctica en uno de
  aventura con semilla, dificultad, layout, estaciones, salida y hash estable.
- `mindcrafted/generator/adventure_rules.py` valida redes y trazas de algoritmos
  con límites acotados y rutas alcanzables.
- `mindcrafted/generator/boss.py` compone un jefe reproducible a partir de tres
  retos ya validados de las lecciones disponibles.
- `mindcrafted/engine/adventure/` incorpora exploración Canvas, controles WASD y
  flechas, interacción con estaciones, encuentros, pausa, dificultad normal,
  tranquila y de estudio, energía, obstáculos, guardado local y jefe final.
- La exportación integra CSS, datos, motor y sprites dentro de `index.html`; no
  depende de rutas `/engine/` al abrir el paquete exportado.
- El servidor conserva el reproductor de práctica y selecciona el reproductor
  correcto según `config.generationMode`.

### Corrección aplicada en esta sesión

En `mindcrafted/generator/adventure.py` se corrigió la composición de layouts:

- La búsqueda de accesibilidad considera una holgura de 16 píxeles alrededor del
  personaje, no solamente un punto central libre.
- Las estaciones se eligen dentro del componente accesible desde `Inicio`.
- Las estaciones deben estar separadas más de 36 píxeles entre sí.
- El portal debe estar separado más de 72 píxeles de cada estación.
- Se devuelven errores claros cuando no existe una ruta o espacio válido.

En `tests/test_adventure.py` se añadió una regresión que verifica la distancia
mínima entre el portal y todas las estaciones para los cuatro mundos y varias
semillas.

En `tests/check_adventure_browser.mjs` se alineó el recorrido automatizado con
el motor: usa la misma holgura de 16 píxeles, conserva el orden de cada tramo
cardinal y espera un frame después de volver del encuentro para leer la posición
actualizada del Canvas.

### Biblioteca visual

- `pixel_worlds/` contiene mapas Tiled, fuentes Aseprite, exportaciones PNG,
  catálogos, previews y scripts de validación.
- Hay cuatro mundos registrados: `technology`, `laboratory`, `mathematics` y
  `biology`.
- Se añadieron recursos de explorador, jefes y escenas tecnológicas mediante el
  flujo local de Aseprite y Tiled, sin MCP ni llamadas a IA durante la exportación.
- `pixel_worlds/scripts/check_assets.py` valida dimensiones, IDs, rutas y
  accesibilidad básica de las interacciones.

## 3. Verificaciones realizadas

Correctas:

    .venv/bin/python -m unittest discover -s tests -p 'test*.py' -v
    .venv/bin/python -m pip check
    .venv/bin/python -m compileall -q mindcrafted tests
    node tests/check_adventure_models.cjs
    python3 pixel_worlds/scripts/check_assets.py
    node pixel_worlds/scripts/check_models.mjs
    node tests/check_adventure_browser.mjs

- La suite Python terminó con 24 pruebas correctas.
- Las pruebas de modelos de aventura y de assets pasaron.
- Los recorridos Chromium de práctica y aventura pasaron.
- El E2E de aventura recorrió cuatro mundos, ocho mecánicas, pausa, derrota sin
  penalización educativa, guardado, vista móvil, HTML exportado y victoria contra
  el jefe en tres fases usando IA simulada.

Nota de entorno: el `python3` del sistema no tiene `httpx`; para pruebas Python
de MindCrafted se debe utilizar `.venv/bin/python`.

## 4. Archivos principales modificados o añadidos

- `mindcrafted/generator/practice.py`: validación, selección de mundos y paquetes.
- `mindcrafted/generator/adventure.py`: layouts, empaquetado y HTML de aventura.
- `mindcrafted/generator/adventure_rules.py`: modelos técnicos acotados.
- `mindcrafted/generator/boss.py`: composición reproducible del jefe.
- `mindcrafted/generator/course_pipeline.py`: integración por curso y lección.
- `mindcrafted/engine/practice/`: reproductor de práctica.
- `mindcrafted/engine/adventure/`: reproductor de aventura.
- `mindcrafted/server.py`: endpoints y selección de reproductor.
- `mindcrafted/static/studio.html`: flujo visual del estudio.
- `tests/test_adventure.py`: regresiones y validación de integración.
- `tests/check_adventure_browser.mjs`: recorrido E2E de aventura.
- `tests/check_practice_browser.mjs`: recorrido E2E de práctica.
- `pixel_worlds/`: arte, mapas, catálogo, scripts y previews.
- `GUIA_GENERADOR_PUZZLES.mk`: guía de uso e integración.
- `mindcrafted/PLAN_AVENTURA_PIXEL_ART.mk`: propuesta original de diseño, ahora
  superada por la implementación en curso.

El worktree ya contenía cambios amplios en otros archivos antes de este resumen.
No se deben revertir ni sobrescribir esos cambios sin revisarlos primero.

## 5. Skills recomendadas

No se instalaron automáticamente. Se documentan los comandos para que la
instalación sea una decisión explícita, especialmente porque algunas skills
pueden añadir archivos, hooks o configuración del agente.

### Prioridad alta

| Skill | Uso en MindCrafted | Instalación |
| --- | --- | --- |
| `test-driven-development` | Añadir primero la regresión y luego corregir generador, motor y API | `npx skills add https://github.com/obra/superpowers --skill test-driven-development` |
| `systematic-debugging` | Investigar el bloqueo del pathfinder sin cambiar pruebas a ciegas | `npx skills add https://github.com/obra/superpowers --skill systematic-debugging` |
| `verification-before-completion` | Exigir pruebas unitarias, assets, exportación y Chromium antes de cerrar una tarea | `npx skills add https://github.com/obra/superpowers --skill verification-before-completion` |
| `webapp-testing` | Automatizar aplicaciones locales con Playwright y ciclo de vida del servidor | `npx skills add https://github.com/anthropics/skills --skill webapp-testing` |

### Prioridad media

| Skill | Uso en MindCrafted | Instalación |
| --- | --- | --- |
| `agent-browser` | Exploración y depuración de la UI desde navegador real | `npx skills add https://github.com/vercel-labs/agent-browser --skill agent-browser` |
| `frontend-design` | Mejorar estudio, reproductores, responsive y jerarquía visual sin caer en layouts genéricos | `npx skills add https://github.com/anthropics/skills --skill frontend-design` |
| `domain-modeling` | Mantener vocabulario y decisiones sobre lecciones, misiones, conceptos y progreso | `npx skills add https://github.com/mattpocock/skills --skill domain-modeling` |
| `improve-codebase-architecture` | Revisar límites entre servidor, generador, motor y assets antes de seguir creciendo | `npx skills add https://github.com/mattpocock/skills --skill improve-codebase-architecture` |

### Para entregables y documentación

| Skill | Uso en MindCrafted | Instalación |
| --- | --- | --- |
| `pptx` | Generar o revisar presentaciones de demo, arquitectura o pitch | `npx skills add https://github.com/anthropics/skills --skill pptx` |
| `pdf` | Extraer, comprobar o producir documentación PDF | `npx skills add https://github.com/anthropics/skills --skill pdf` |
| `planning-with-files` | Mantener plan, hallazgos y progreso entre sesiones largas | `npx skills add https://github.com/othmanadi/planning-with-files --skill planning-with-files` |
| `archify` | Crear diagramas HTML interactivos de arquitectura o flujo | `npx skills add https://github.com/tt-a1i/archify --skill archify` |

## 6. Orden recomendado para continuar

1. Instalar únicamente `test-driven-development`, `systematic-debugging`,
   `verification-before-completion` y `webapp-testing`.
2. Mantener sincronizados `layout`, `AdventureCore.walkable` y los drivers E2E
   cuando se añadan mapas o nuevas colisiones.
3. Repetir todas las verificaciones del apartado 3 después de cada cambio.
4. Solo después pulir UI, documentación de demo y nuevos mundos.

## 7. Fuentes consultadas

- https://skills.sh/obra/superpowers/test-driven-development
- https://skills.sh/obra/superpowers/systematic-debugging
- https://skills.sh/obra/superpowers/verification-before-completion
- https://skills.sh/anthropics/skills/webapp-testing
- https://skills.sh/vercel-labs/agent-skills/agent-browser
- https://skills.sh/anthropics/skills/frontend-design
- https://skills.sh/mattpocock/skills/domain-modeling
- https://skills.sh/mattpocock/skills/improve-codebase-architecture
- https://skills.sh/anthropics/skills/pptx
- https://skills.sh/anthropics/skills/pdf
- https://skills.sh/othmanadi/planning-with-files/planning-with-files
- https://skills.sh/tt-a1i/archify/archify
- https://opencode.ai/docs/skills/
