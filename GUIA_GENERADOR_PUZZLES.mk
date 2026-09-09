# Guía del generador de puzzles de MindCrafted

Actualizada: 8 de septiembre de 2026.
Este archivo es documentación en texto/Markdown con la extensión .mk solicitada.
No es un Makefile: léelo en tu editor; no se ejecuta con make.

## 1. Qué hace ahora el proyecto

El estudiante sube un PDF o PowerPoint, o pega apuntes en Markdown. Revisa las
lecciones extraídas y genera un curso. Cada lección produce entre 3 y 5 puzzles,
combinando al menos dos mecánicas apropiadas para su contenido. El generador
selecciona un mundo pixel art y prepara un juego con instrucciones, pistas,
explicaciones y fragmentos de los apuntes que se pueden consultar.

La IA propone los datos educativos. El programa local valida el plan y ejecuta
las reglas del juego. No necesita que la IA escriba JavaScript para cada reto.
Aseprite y Tiled aportan la biblioteca visual; no hay conexión MCP.

Hay tres mundos reutilizables, no un escenario dibujado desde cero por cada
subida. Lo que cambia entre lecciones son los conceptos, datos, retos y su
combinación. La variedad se solicita a la IA, pero no se garantiza que dos
subidas del mismo material produzcan planes distintos.

## 2. Iniciar y utilizar el estudio

Ejecuta estos comandos desde la raíz de MindCrafted. Si ya tienes el entorno
virtual y las dependencias, basta con el último comando.

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    bash start.sh

Abre http://127.0.0.1:8000/ en tu navegador.

El proveedor de IA se configura con API_KEY, API_BASE_URL y MODEL en .env, o
con los campos de configuración del estudio. Usa el identificador de un modelo
que esté disponible en tu proveedor y admita las solicitudes de chat utilizadas
por el adaptador existente. No copies claves a la guía, al repositorio ni a los
archivos de práctica. La integración usa el proveedor ya configurado.

Recorrido:

1. Sube PDF/PPTX o pega apuntes. Importar convierte el archivo a texto; todavía
   no crea juegos ni llama al generador de puzzles.
2. Analiza el contenido y revisa los títulos, la materia y el texto de cada
   lección. Corrige errores de extracción antes de generar.
3. Pulsa el botón para generar. Se procesa una lección tras otra.
4. Abre una lección lista. Usa los botones del mapa para elegir un puzzle.
5. Manipula el ejercicio y pulsa Comprobar. Puedes pedir una pista o consultar
   el fragmento de los apuntes. Una respuesta incorrecta permite otro intento.
6. Completa los retos y avanza a la siguiente lección. Reiniciar reto conserva
   el mejor resultado y permite repetir el ejercicio.

La pestaña de cursos abre la página del curso para elegir una lección; admite
identificadores personalizados y cursos con alguna lección fallida.

## 3. Preparar buenos apuntes

Incluye reglas, relaciones, ejemplos y explicaciones. Un título o una lista de
palabras no suelen aportar material suficiente para tres retos fundamentados.
Para ordenar etapas, escribe un proceso con un orden claro. Para practicar
álgebra, incluye ecuaciones y operaciones permitidas. Para circuitos, explica
la relación entre voltaje, resistencia y corriente.

Ejemplo para pegar en el estudio:

    # Práctica de matemáticas
    ## Igualdades y fracciones
    Una ecuación conserva la igualdad al aplicar la misma operación en ambos
    miembros. Para resolver 2x + 4 = 14, resta cuatro a ambos lados y divide
    entre dos. Una fracción representa partes iguales de un todo: el numerador
    cuenta las partes elegidas y el denominador indica el total de partes
    iguales. Tres cuartos significa elegir tres de cuatro partes iguales.

El encabezado # es el curso y cada ## crea una lección. El contenido evaluado
es el texto de esa lección, no solamente su título ni el nombre de la materia.

Límites actuales:

- PDF: hasta 25 MB y 150 páginas; se extrae texto, sin OCR para escaneos.
- PPTX: hasta 25 MB y 200 diapositivas. El formato antiguo .ppt no se admite.
- Los importadores agrupan el material en hasta 12 secciones.
- Generación: hasta 24 lecciones y 300.000 caracteres en total.
- Cada lección debe contener entre 60 y 60.000 caracteres para generar puzzles.
- Cada lección genera de 3 a 5 puzzles y al menos dos tipos diferentes.

Estos límites técnicos no aseguran que el texto sea suficiente en lo educativo.
Diagramas, imágenes y fórmulas que el importador no convierta correctamente en
texto deben explicarse o corregirse antes de generar.

## 4. Mundos y mecánicas disponibles

| Mundo | Uso previsto | Ejemplos de práctica |
| --- | --- | --- |
| mathematics | Matemáticas; aula para humanidades | Despejar ecuaciones, construir fracciones, relacionar conceptos |
| laboratory | Física, química y tecnología | Ajustar un circuito de Ohm, asociar magnitudes, aplicar reglas |
| biology | Biología y ecología | Ordenar germinación, relacionar órganos y funciones, explicar casos |

Un puzzle de circuitos fuerza el laboratorio; uno numérico fuerza matemáticas
si no hay circuito en la lección. Para los demás, la IA elige entre los tres
mundos según el tema. Humanidades reutiliza el aula: no tiene todavía arte ni
mecánicas especializadas para cada disciplina.

| Tipo interno | Interacción del estudiante | Datos validados |
| --- | --- | --- |
| balance_equation | Aplicar operaciones a ambos lados hasta aislar x | a, b, c; solución entera calculada localmente |
| fraction_fill | Seleccionar partes iguales de un todo | numerator y denominator |
| circuit_target | Ajustar voltaje y cerrar un circuito hasta alcanzar la corriente objetivo | resistance y target_voltage; I calculada localmente |
| concept_links | Conectar conceptos con sus relaciones en columnas mezcladas | 3–5 pares únicos left/right |
| process_order | Subir o bajar pasos para reconstruir un proceso | 3–6 steps en orden correcto |
| evidence_choice | Resolver una situación eligiendo una opción | 3–4 options y answer desde cero |

El circuito es un modelo ideal de corriente continua, con resistencia total
fija y una batería de 0 a 24 V. No simula componentes reales complejos.
La fracción usa partes del mismo tamaño. La ecuación es lineal de una incógnita.

La detección de vocabulario habilita álgebra, fracciones y circuitos cuando el
texto menciona sus conceptos. No obliga a usar todos los tipos habilitados.
La IA recibe las mecánicas usadas antes para favorecer variedad entre lecciones.

## 5. Arquitectura y archivos

Flujo:

    PDF/PPTX/Markdown
      -> importador y editor del estudio
      -> /api/generate
      -> course_pipeline.generate_course
      -> pipeline.generate_game (fast_mode=True)
      -> practice.generate_practice
      -> plan JSON de IA -> validate_plan
      -> load_world -> paquete y HTML
      -> reproductor de práctica

Archivos principales:

- mindcrafted/generator/practice.py: prompt, selección de mecánicas, validación,
  empaquetado del arte y creación del HTML.
- mindcrafted/generator/pipeline.py: conecta la ruta predeterminada al generador
  de práctica. fast_mode=False conserva la ruta anterior de simulaciones.
- mindcrafted/generator/course_pipeline.py: recorre lecciones, registra resultados
  y resuelve la navegación siguiendo el orden de las lecciones que tuvieron éxito.
- mindcrafted/server.py: importación, tareas, API del paquete y elección del
  reproductor según config.generationMode.
- mindcrafted/static/studio.html: revisión de apuntes y progreso de generación.
- mindcrafted/engine/practice/: player.html, style.css y runtime.js.
- mindcrafted/engine/bkt.js: estimación de dominio guardada en el navegador.
- pixel_worlds/: originales Aseprite, mapas Tiled y exportaciones.

Salida por curso, dentro de courses/<curso>/:

- _content.json: contenido revisado enviado al generador.
- course-manifest.json: estado, mundo y cantidad de puzzles de cada lección.
- index.html: página de selección de lecciones.
- games/<leccion>/practice-plan.json: plan educativo validado y legible.
- games/<leccion>/game.pkg.json: configuración, puzzles, mapa y PNG integrados.
- games/<leccion>/index.html: práctica con JS, CSS y datos integrados.
- games/<leccion>/cover.js: portada compatible con la página del curso.

Los paquetes incluyen el arte como datos PNG; el estudiante no necesita instalar
Aseprite ni Tiled. El HTML exportado incluye el motor y los datos. La fuente
personalizada y los enlaces entre lecciones siguen usando rutas del servidor;
para conservar esa navegación, comparte el curso servido por MindCrafted.

MINDCRAFTED_HOME permite separar courses/, jobs/, assets/ y courses.json.
MINDCRAFTED_PIXEL_WORLDS permite indicar otra ruta absoluta a la biblioteca de
arte. Cuando no se define, se usa pixel_worlds/ de este repositorio. Si distribuyes
el programa fuera del repositorio, debes distribuir también esa biblioteca.

## 6. Validación y errores

La respuesta de IA debe ser JSON con subject, world, introduction y puzzles.
Cada puzzle requiere kind, title, instruction, concept, hint, explanation,
evidence y data. El esquema completo está descrito en practice_prompt().

Se comprueba que:

- La mecánica esté permitida por el vocabulario de los apuntes.
- La evidencia esté contenida en el texto de la lección, normalizando mayúsculas,
  Unicode y espacios; debe tener entre 20 y 700 caracteres.
- Las cantidades estén dentro de los rangos y los problemas numéricos tengan
  solución. El servidor calcula la solución de ecuaciones y la corriente.
- Las opciones, relaciones y pasos no estén repetidos ni vacíos.
- No existan puzzles con la misma mecánica y los mismos datos dentro del plan.
- El plan tenga de 3 a 5 puzzles y al menos dos mecánicas.

Si el plan no pasa, se solicita una reparación completa una sola vez. Si tampoco
pasa, la lección queda fallida. No se sustituye por preguntas genéricas. El
adaptador del proveedor también puede reintentar errores de transporte: una
reparación de contenido no equivale a un límite absoluto de dos solicitudes HTTP.

La evidencia literal demuestra que el fragmento existe; no prueba que toda la
interpretación de la IA sea correcta. Las respuestas conceptuales y el orden de
procesos los propone la IA: conviene revisar los planes antes de usarlos en una
evaluación formal. La comprobación automática es más fuerte para las reglas
numéricas implementadas que para explicaciones abiertas.

Si unas lecciones fallan, el estudio muestra el resultado parcial y permite
practicar las listas. La navegación salta las fallidas y conserva el orden del
manifiesto, aunque los IDs sean chunk-2, chunk-10 u otros nombres.
Si ninguna se genera, la tarea termina con error. Revisa credenciales y texto.
Para volver a intentar desde el estudio, corrige el material y genera un curso
nuevo. Esta ruta no reanuda checkpoints ni regenera solamente las fallidas.

## 7. Editar el pixel art con Aseprite y Tiled

No se usa MCP. Aseprite se ejecuta por su interfaz o en modo batch; Tiled edita
los mapas y su terminal exporta copias y vistas previas.

1. Abre pixel_worlds/art/source/*.aseprite para cambiar piezas y animaciones.
2. Abre pixel_worlds/MindCrafted.tiled-project y edita maps/*.tmj.
3. Conserva el tamaño de mapa 24 × 16, los tiles de 32 px y el atlas de terreno
   de 8 columnas. El reproductor actual asume esas dimensiones.
4. Conserva la capa Suelo y la capa de objetos Escenario. Cada objeto necesita
   asset_id en sus propiedades y debe estar registrado en manifest.json.
5. Exporta desde la raíz del proyecto:

    ASEPRITE_BIN="$HOME/aseprite/build/bin/aseprite"
    PIXEL_ROOT="$PWD/pixel_worlds"
    "$ASEPRITE_BIN" --batch --script-param "root=$PIXEL_ROOT" --script pixel_worlds/scripts/export_assets.lua
    python3 pixel_worlds/scripts/export_maps.py
    "$ASEPRITE_BIN" --batch --script-param "root=$PIXEL_ROOT" --script pixel_worlds/scripts/compose_scenes.lua
    python3 pixel_worlds/scripts/check_assets.py

Ajusta la ruta del binario a tu instalación. Los exportadores conservan el dibujo
manual; build.py vuelve a dibujar los originales. Para reconstruir una copia:

    python3 pixel_worlds/scripts/build.py --aseprite "$HOME/aseprite/build/bin/aseprite" --output /tmp/mindcrafted-art-nuevo

--replace-art autoriza sustituir los originales: no lo uses para una exportación
normal. Consulta pixel_worlds/README.md para las capas y el flujo completo.

Las escenas completas en scenes/ son copias editables independientes. Editarlas
no actualiza automáticamente los mapas. Para modificar la composición que ve el
estudiante, edita Tiled. Tras exportar, genera una práctica nueva: los paquetes
existentes guardan una copia del arte y no cambian retroactivamente.

El reproductor de práctica dibuja Suelo y Escenario. Sus marcadores representan
los puzzles del plan; no ejecuta automáticamente los hotspots Interacciones del
atlas de demostración. Colisiones e Inicio se reservan para movimiento futuro;
el personaje sigue siendo ambiental, sin controles de desplazamiento.

Para un cuarto mundo hay que ampliar también THEMES, el prompt y las reglas de
selección en practice.py; añadir archivos al catálogo por sí solo no lo habilita.
Para una mecánica nueva, agrega validador, esquema del prompt, interacción en
runtime.js y pruebas de resolución. Mantén las reglas ejecutables locales.

## 8. Progreso del estudiante

Los intentos, pistas, mejores puntos y retos completados se guardan en
localStorage. Se distinguen por curso, lección y hash del plan para evitar que
una práctica diferente herede retos completados.

La puntuación correcta parte de 100: resta 10 por intento anterior y 5 por pista,
con un mínimo de 40. Se conserva la puntuación máxima obtenida en cada reto.
La estimación BKT registra aciertos por concepto dentro del curso; no es una
calificación oficial. No hay sincronización entre dispositivos ni separación
por cuentas de estudiante en esta implementación. Borrar datos del navegador
elimina el progreso local.

Los controles permiten usar teclado, consultar texto fuera del canvas y reducir
animaciones. Hay diseño adaptable a móvil y un botón para pausar animaciones.

## 9. Pruebas reproducibles

Pruebas automatizadas de Python:

    .venv/bin/python -m unittest discover -s tests
    node --check mindcrafted/engine/practice/runtime.js

Cubren la importación existente, BKT, ensamblado del curso, planes por materia,
evidencias inexistentes, duplicados, problemas irresolubles, reparación acotada,
rechazo sin contenido genérico, empaquetado y navegación con fallos intermedios.

Prueba integral en navegador, con Node >=22 y Chromium instalados:

    .venv/bin/python tests/create_practice_upload.py
    .venv/bin/python tests/serve_practice_fixture.py

En otra terminal:

    chromium --headless --no-sandbox --disable-gpu --disable-dev-shm-usage --remote-debugging-address=127.0.0.1 --remote-debugging-port=9228 --user-data-dir=/tmp/mindcrafted-practice-chromium about:blank

En una tercera terminal:

    node tests/check_practice_browser.mjs

Este servidor escucha solo en 127.0.0.1:8022, usa un directorio temporal y una IA
simulada. Nunca añade respuestas simuladas al servidor normal. --no-sandbox se
usa únicamente en este navegador aislado de prueba, con contenido local.
Detén ambos servidores de prueba con Ctrl+C cuando termines.

El test sube un PowerPoint real, analiza el Markdown, genera un curso parcial,
abre tres mundos, rechaza respuestas incompletas, resuelve las seis mecánicas,
comprueba pistas, persistencia, HTML exportado, móvil y movimiento reducido.
Las capturas quedan en /tmp/mindcrafted-practice-check/previews/.

Estas pruebas verifican el programa con respuestas controladas. No prueban la
calidad de un modelo remoto ni consumen una API real. Para evaluar tu proveedor,
genera desde el estudio con apuntes representativos y revisa practice-plan.json
junto con los juegos resultantes.

## 10. Resolver problemas habituales

- “No se encuentra pixel_worlds/manifest.json”: restaura la carpeta completa o
  configura MINDCRAFTED_PIXEL_WORLDS con una biblioteca exportada compatible.
- “La evidencia no aparece”: revisa la extracción del documento. Si se repite,
  cambia o amplía el texto; el generador ya intentó una reparación.
- “No se pudo generar ningún juego”: revisa los errores de la tarea, la clave,
  la URL del proveedor, el modelo y la suficiencia de las lecciones.
- Solo aparecen juegos antiguos: abre un curso recién generado. Los paquetes
  anteriores conservan su reproductor; no se convierten automáticamente.
- No aparecen los cambios de arte: exporta desde Aseprite/Tiled y genera un curso
  nuevo, ya que los paquetes anteriores incluyen sus propias imágenes.
- El servidor sigue mostrando la versión anterior: detén y reinicia start.sh.
- Un PDF escaneado queda vacío: convierte primero las imágenes a texto mediante
  OCR externo, revisa el resultado y pégalo como apuntes.
- Se perdió el progreso: comprueba que estás en el mismo navegador y origen;
  localhost y 127.0.0.1 tienen almacenamiento distinto.

Referencias del proyecto: pixel_worlds/README.md,
pixel_worlds/docs/ART_DIRECTION.md y mindcrafted/generator/practice.py.
