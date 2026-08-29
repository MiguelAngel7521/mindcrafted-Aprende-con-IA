# Documentación integral de MindCrafted

> Contexto funcional y técnico para personas y agentes de IA que necesiten entender, mantener o integrar este repositorio con otro proyecto.

| Dato | Valor verificado en el código local |
|---|---|
| Nombre del paquete | `mindcrafted` |
| Versión | `0.1.1` |
| Tipo de producto | Estudio autoalojado de aprendizaje basado en juegos e IA |
| Entrada principal | Material educativo en Markdown |
| Salida principal | Microcurso con juegos web reproducibles |
| Backend | Python, FastAPI y Uvicorn |
| Frontend | HTML, CSS y JavaScript sin framework |
| Motor de juego | JavaScript, Canvas 2D y WebGL decorativo |
| Protocolo de IA | Chat Completions compatible con OpenAI |
| Proveedor predeterminado | OpenRouter |
| Persistencia | Archivos locales JSON, HTML y JavaScript |
| Base de datos | Ninguna |
| Puerto principal | `8000` |
| Puerto Node auxiliar | `3100` |
| Licencia | AGPL-3.0-or-later |
| Fecha de esta revisión | 29 de agosto de 2026 |

El código vigente de este checkout usa el paquete `mindcrafted`. Los archivos fuente listados aquí son la referencia para integrar el proyecto.

---

## 1. Resumen para otra IA

MindCrafted convierte contenido educativo escrito en Markdown en experiencias jugables para navegador. Cada encabezado `##` del documento se transforma en una lección independiente. Para cada lección, un pipeline de IA genera:

- una estructura pedagógica;
- una narrativa con personajes y diálogos;
- capítulos internos;
- una simulación interactiva por capítulo;
- iconos, personajes, fondos y portada en pixel art programado;
- textos localizados;
- configuración de audio, progreso, puntaje y XP;
- un HTML ensamblado y un paquete JSON reproducible.

El proyecto no usa base de datos, cuentas, contenedores ni infraestructura cloud. FastAPI guarda los cursos en `courses/`, los estados resumidos de generación en `jobs/` y el índice en `courses.json`.

Para unirlo rápidamente con otro proyecto de hackathon, la opción recomendada es ejecutarlo como un servicio separado y consumir sus endpoints HTTP. El proyecto principal debería encargarse de usuarios, autorización, base de datos y despliegue; MindCrafted puede encargarse de transformar material educativo en juegos.

### Representación compacta

```yaml
name: MindCrafted
package: mindcrafted
version: 0.1.1
goal: material educativo -> curso de juegos web
input:
  format: Markdown o JSON estructurado
  lesson_boundary: encabezado Markdown ##
output:
  course_manifest: courses/{course_id}/course-manifest.json
  course_page: courses/{course_id}/index.html
  game_package: courses/{course_id}/games/{chunk_id}/game.pkg.json
  game_html: courses/{course_id}/games/{chunk_id}/index.html
runtime:
  api: FastAPI
  ai: OpenAI-compatible API
  browser: Canvas 2D + JavaScript dinámico
  state: filesystem + localStorage
integration:
  recommended: servicio HTTP independiente
  create: POST /api/generate
  status: GET /api/jobs/{job_id}
  manifest: GET /api/courses/{course_id}/manifest
  play: GET /play?course={course_id}&game={chunk_id}
important_gaps:
  - no hay autenticación de servidor
  - engine.js llama un endpoint de reportes no implementado
  - el código generado por IA se ejecuta en el navegador
license: AGPL-3.0-or-later
```

---

## 2. Problema que resuelve y para qué sirve

Producir un recurso educativo interactivo exige normalmente contenido, diseño, narrativa y programación. MindCrafted automatiza una gran parte de ese trabajo:

1. recibe apuntes, un temario, una guía o un capítulo de libro;
2. estructura el conocimiento por lecciones;
3. convierte cada lección en una historia educativa;
4. crea simulaciones relacionadas con los conceptos;
5. genera la dirección visual mediante pixel art programado;
6. valida y repara parte del código generado;
7. entrega un curso jugable en el navegador.

Casos de uso posibles:

- prototipos de educación gamificada;
- microlearning y repaso;
- demostraciones interactivas de conceptos;
- material personalizado por edad, nivel o idioma;
- función “texto a juego” dentro de otra plataforma;
- generación rápida de experiencias para una hackathon educativa.

---

## 3. Funcionalidades reales

### Implementadas

- Landing page y Studio web.
- Editor y previsualización básica de Markdown.
- Parser Markdown a JSON estructurado.
- Edición de título, subtítulo, materia, nivel, contenido y tema por lección.
- Configuración de clave, modelo y base URL de IA.
- Compatibilidad con OpenRouter y otros proveedores que implementen Chat Completions de OpenAI.
- Prueba de conexión desde el Studio.
- Generación asíncrona de cursos.
- Polling de progreso y logs filtrados.
- Checkpoints para reutilizar pasos tras una interrupción.
- Generación de un juego por lección.
- Generación de una simulación personalizada por capítulo interno.
- Fallback genérico si una simulación falla.
- Validación sintáctica y ejecución simulada de JavaScript.
- Ensamblado de HTML y paquete JSON.
- Listado, reproducción y eliminación de cursos locales.
- Reproductor con Canvas, diálogos, audio, capítulos, XP, niveles y estrellas.
- Progreso y nombre de jugador en `localStorage`.
- Ocho idiomas de interfaz/salida.
- Veinticuatro temas visuales.

### No implementadas en este repositorio

- Base de datos.
- Usuarios, sesiones, roles o autorización en FastAPI.
- Pagos, créditos o compras.
- Almacenamiento remoto S3/R2.
- Cola distribuida, Redis o workers externos.
- Panel administrativo multiusuario.
- Backend de analítica.
- Backend para reportar errores de minijuegos.
- Suite de tests de producto.
- Dockerfile o despliegue reproducible.

El código contiene hooks de autenticación, pagos y analítica de una plataforma alojada, pero no sus implementaciones.

---

## 4. Flujo funcional

```mermaid
flowchart LR
    U[Usuario escribe Markdown] --> P[POST /api/parse-md-text]
    P --> S[Usuario revisa estructura y temas]
    S --> G[POST /api/generate]
    G --> J[Job en segundo plano]
    J --> AI[Proveedor de IA]
    AI --> V[Validar y reparar JSON/JS]
    V --> A[Ensamblar curso y juegos]
    A --> D[(courses/ y courses.json)]
    D --> R[/play carga game.pkg.json]
    R --> C[Motor Canvas en navegador]
```

Markdown esperado:

```markdown
# Introducción a la física

Curso para comprender movimiento y fuerzas.

- Comprender la velocidad
- Reconocer fuerzas comunes

## Movimiento

La posición de un objeto cambia con el tiempo.

### Velocidad media

- Se calcula como distancia entre tiempo

## Fuerzas

Una fuerza puede cambiar el movimiento de un objeto.
```

Reglas del parser:

- `#` define el título del curso.
- El texto posterior y anterior al primer `##` forma la descripción.
- Las listas de esa zona se guardan como objetivos generales.
- Cada `##` crea un `chunk`, es decir, una lección/juego.
- El primer `###` de un chunk se usa también como subtítulo.
- Los IDs se crean como `chunk-1`, `chunk-2`, etc.
- Los temas se asignan en rotación y luego pueden editarse.

---

## 5. Arquitectura

```mermaid
flowchart TB
    subgraph Browser
        Landing[Landing HTML]
        Studio[Studio HTML/JS]
        Player[Player HTML]
        Engine[engine.js + Canvas]
        LS[(localStorage)]
    end

    subgraph Python[FastAPI :8000]
        Routes[Rutas API]
        Parser[Parser Markdown]
        Jobs[JobManager]
        Pipeline[Pipeline IA]
        Static[StaticFiles]
    end

    subgraph Node[Node :3100]
        State[/state y /next]
    end

    AI[API compatible con OpenAI]
    Disk[(courses/ jobs/ assets/)]

    Studio --> Routes
    Player --> Routes
    Player --> Engine
    Engine --> LS
    Routes --> Parser
    Routes --> Jobs
    Jobs --> Pipeline
    Pipeline --> AI
    Pipeline --> Disk
    Static --> Disk
    Routes --> State
```

### Componentes y responsabilidades

| Archivo | Función |
|---|---|
| `server.py` | Entrada ASGI que reexporta `mindcrafted.server:app`. |
| `mindcrafted/server.py` | FastAPI, configuración, CORS, jobs, cursos, reproducción y archivos estáticos. |
| `mindcrafted/static/index.html` | Landing page. |
| `mindcrafted/static/studio.html` | Editor, configuración de IA, progreso y lista de cursos. |
| `mindcrafted/generator/api.py` | Cliente `AsyncOpenAI`, reintentos, concurrencia y selección de modelo. |
| `mindcrafted/generator/prompts.py` | Prompts de conocimiento, narrativa, arte y simulación. |
| `mindcrafted/generator/pipeline.py` | Generación completa de un juego. |
| `mindcrafted/generator/course_pipeline.py` | Generación secuencial de juegos y manifiesto del curso. |
| `mindcrafted/generator/assembler.py` | Une plantilla, motor, guion, arte y minijuegos. |
| `mindcrafted/generator/course_assembler.py` | Genera la página de presentación/navegación del curso. |
| `mindcrafted/generator/package_builder.py` | Crea `game.pkg.json` y soporte opcional de cifrado. |
| `mindcrafted/generator/i18n.py` | Strings para ocho idiomas. |
| `mindcrafted/generator/sandbox.py` | Valida JS con Node o Esprima y genera prompts de reparación. |
| `mindcrafted/generator/sandbox_harness.js` | DOM y Canvas simulados para probar código generado. |
| `mindcrafted/engine/engine.js` | Runtime de narrativa, juego, XP, audio y progreso. |
| `mindcrafted/engine/player.html` | Descarga el paquete e inyecta motor, arte y simulaciones. |
| `mindcrafted/engine/template.html` | Plantilla Jinja2 del HTML ensamblado. |
| `mindcrafted/engine/minigames/simulation.js` | Simulación genérica de respaldo. |
| `mindcrafted/node/server.js` | Servicio HTTP auxiliar de estado. |
| `mindcrafted/node/engine-state.js` | Máquina de estados para el guion. |

---

## 6. Pipeline de IA

Por cada lección, `generate_game()` ejecuta:

1. **Descomposición de conocimiento:** título, conceptos, capítulos, personajes, ambientación, iconos y sugerencias de simulación.
2. **Generación paralela:** diálogos, iconos, sprites, fondos, portada y simulaciones.
3. **Reparación defensiva:** limpieza de JSON truncado, validación de estructuras y corrección de referencias `sim_N`.
4. **Revisión visual:** una segunda llamada pule el pixel art.
5. **Validación JS:** Node ejecuta el código con un DOM simulado; Esprima es fallback de sintaxis.
6. **Fallback:** si una simulación falla, se usa código genérico.
7. **Ensamblado:** Jinja2 combina motor, datos y arte.
8. **Empaquetado:** se escriben HTML, JSON, portada e idioma.

El cliente limita la concurrencia global de llamadas de IA a dos. Las lecciones de un curso se generan secuencialmente, mientras varias tareas internas de cada juego se ejecutan en paralelo.

### Checkpoints

Durante el trabajo se crea:

```text
courses/{course_id}/games/{chunk_id}/_checkpoint.json
```

Puede contener `knowledge`, `dialog`, `pixel_icons`, `pixel_chars`, `pixel_backgrounds`, `cover_art`, `sim_0`, `sim_1` y arte revisado. Si se repite el mismo `course_id`, los pasos existentes se reutilizan. Al completar correctamente se elimina el checkpoint.

### Modelos por etapa

Además de `MODEL`, se puede usar `STUDIO_MODEL_<ETAPA>` para:

```text
knowledge
dialog
pixel_icons
pixel_chars
pixel_backgrounds
cover_art
sim_visual_objects
sim_design
sim_implement
sim_judge
sim_refine
review_batch
minigame_icons
```

---

## 7. Tecnologías

### Python

- Python `>=3.10`; el entorno local usa `3.14.7`.
- FastAPI y Uvicorn.
- `httpx`.
- SDK `openai` con `AsyncOpenAI`.
- `python-dotenv`.
- Jinja2.
- Esprima.
- `asyncio`, `contextvars` y filesystem estándar.

Dependencias recuperadas de `mindcrafted.egg-info/PKG-INFO`:

```text
fastapi>=0.100.0
uvicorn[standard]>=0.22.0
python-multipart>=0.0.6
aiofiles>=23.0.0
httpx>=0.24.0
python-dotenv>=1.0.0
openai>=1.0.0
esprima>=4.0.1
jinja2>=3.1.0
```

### Navegador

- HTML5, CSS3 y JavaScript puro.
- Canvas 2D para pixel art.
- WebGL para el ruido decorativo.
- Elementos `Audio` para música y efectos `.ogg`.
- `localStorage` y `sessionStorage`.
- Sin React, Vue, Angular ni bundler.

### Node.js

- Requiere Node `>=18`; este entorno tiene `v26.7.0`.
- Servicio auxiliar construido con `http`, sin dependencias NPM obligatorias.
- El empaquetador intenta usar `npx terser` para minificación.

### Opcionales

- `cryptography` para paquetes Fernet cifrados; no está declarada como dependencia principal.
- Terser para minificación/obfuscación.

### Infraestructura del repositorio

- GitHub Actions para construir un wheel/sdist.
- Workflow de publicación a PyPI mediante tags `v*`.
- No hay Docker, base de datos, Redis ni servicios cloud configurados.

---

## 8. Estructura de archivos

```text
MindCrafted/
├── .env                         # Secretos locales; ignorado por Git
├── .github/workflows/           # CI y publicación
├── assets/audio/                # Música y SFX .ogg
├── courses/                     # Cursos generados
├── jobs/                        # Snapshots de jobs
├── mindcrafted/
│   ├── server.py
│   ├── static/
│   │   ├── index.html
│   │   └── studio.html
│   ├── engine/
│   │   ├── engine.js
│   │   ├── player.html
│   │   ├── template.html
│   │   └── minigames/simulation.js
│   ├── generator/
│   │   ├── api.py
│   │   ├── prompts.py
│   │   ├── pipeline.py
│   │   ├── course_pipeline.py
│   │   ├── assembler.py
│   │   ├── course_assembler.py
│   │   ├── package_builder.py
│   │   ├── i18n.py
│   │   ├── sandbox.py
│   │   └── sandbox_harness.js
│   ├── node/
│   │   ├── package.json
│   │   ├── server.js
│   │   └── engine-state.js
│   └── readme/                  # Capturas y demos
├── server.py
├── start.sh
├── LICENSE
└── DOCUMENTACION_PROYECTO.md
```

`mindcrafted.egg-info/`, `mindcrafted_V1/` y `mindcrafted_V2/` son artefactos locales de instalación/entorno virtual y no deben tratarse como código fuente. `edgameclaw/` es un adaptador de compatibilidad para el comando solicitado.

Salida generada:

```text
courses.json
courses/{course_id}/
├── _content.json
├── course-manifest.json
├── index.html
└── games/{chunk_id}/
    ├── index.html
    ├── game.pkg.json
    ├── game.pkg.enc             # Solo si el cifrado funciona
    ├── cover.js
    ├── _checkpoint.json         # Temporal
    └── locales/{locale}.json

jobs/{job_id}.json
```

---

## 9. Contratos de datos

### Entrada estructurada central

```json
{
  "course": {
    "title": "Introducción a la física",
    "subtitle": "Movimiento y fuerzas",
    "description": "Curso introductorio",
    "subject": "Física",
    "level": "Secundaria",
    "estimated_time": "30 minutos",
    "learning_objectives": ["Comprender velocidad"],
    "tags": ["STEM"]
  },
  "chunks": [
    {
      "id": "chunk-1",
      "title": "Movimiento",
      "subtitle": "Posición, tiempo y velocidad",
      "theme": "ocean-dream",
      "learning_objectives": ["Calcular velocidad media"],
      "content": "Texto educativo completo"
    }
  ]
}
```

Mínimos validados por `/api/generate`:

- `course.title` no vacío;
- al menos un elemento en `chunks`;
- clave de IA en el request o entorno.

Los IDs solo aceptan letras, números, `_`, `-` y `.`. Se rechazan `/`, `\` y `..`.

### Manifiesto

```json
{
  "course": {},
  "games": [
    {
      "chunk_id": "chunk-1",
      "title": "Movimiento",
      "subtitle": "Posición, tiempo y velocidad",
      "theme": "ocean-dream",
      "html_path": "/ruta/local/index.html",
      "cover_js_src": "games/chunk-1/cover.js",
      "learning_objectives": [],
      "mechanics": ["sim_0"],
      "status": "success"
    }
  ],
  "generated_at": "2026-08-29T15:00:00"
}
```

Si un juego falla conserva su entrada con `status: "failed"` y `error`.

### Job

```json
{
  "id": "a1b2c3d4e5",
  "course_id": "curso-demo",
  "status": "running",
  "logs": [{"t": 1788012345.2, "msg": "{\"type\":\"substep\",\"pct\":50}"}],
  "result": null,
  "error": null,
  "created_at": 1788012345.0
}
```

Estados: `running`, `completed`, `failed`.

Los elementos `logs[].msg` pueden contener JSON serializado como string. El cliente debe intentar parsearlo y conservar el texto si no es JSON.

### Paquete de juego

```json
{
  "v": 1,
  "config": {},
  "script": [],
  "pixel_art_js": "...",
  "minigames_js": "...",
  "cover_js": "...",
  "init_js": "...",
  "styleBlock": "<style>...</style>",
  "theme": {},
  "ui": {},
  "title": "Título",
  "subtitle": "Subtítulo",
  "total_chapters": 6
}
```

Este JSON contiene JavaScript generado y debe tratarse como código activo.

### Guion

```json
[
  {"type": "bg", "bg": 0, "chars": []},
  {"type": "chapter", "chapter": 0},
  {"type": "dialog", "speaker": "mentor", "text": "Hola"},
  {"type": "minigame", "game": "sim_0"},
  {"type": "end"}
]
```

El motor del navegador procesa el guion localmente. Node implementa una máquina equivalente, pero el reproductor actual no consume sus rutas.

---

## 10. API HTTP

| Método | Ruta | Responsabilidad |
|---|---|---|
| `GET` | `/` | Landing. |
| `GET` | `/studio` | Estudio. |
| `GET` | `/play` | Reproductor con query `course` y `game`. |
| `GET` | `/api/config` | Modelo, base URL y presencia de clave sin exponerla. |
| `POST` | `/api/parse-md-text` | Markdown a JSON. |
| `POST` | `/api/generate` | Inicia generación en background. |
| `GET` | `/api/jobs/{job_id}` | Estado y logs del job. |
| `GET` | `/api/courses` | Lista cursos. |
| `GET` | `/courses.json` | Alias del listado. |
| `GET` | `/api/courses/{course_id}/manifest` | Manifiesto. |
| `DELETE` | `/api/courses/{course_id}` | Borra el directorio del curso. |
| `POST` | `/api/ai-chat` | Proxy de prueba a `/chat/completions`. |
| `GET` | `/api/play/{course_id}/{chunk_id}/package` | Entrega `game.pkg.json`. |
| `POST` | `/api/play/{course_id}/{chunk_id}/state` | Proxy a Node `/state`. |
| `POST` | `/api/play/{course_id}/{chunk_id}/next` | Proxy a Node `/next`. |

Montajes estáticos:

```text
/static   -> mindcrafted/static/
/engine   -> mindcrafted/engine/
/courses  -> courses/
/assets   -> assets/
/readme   -> mindcrafted/readme/
```

### Analizar

```http
POST /api/parse-md-text
Content-Type: application/json

{"markdown":"# Curso\n\nDescripción\n\n## Lección 1\n\nContenido"}
```

### Generar

```http
POST /api/generate
Content-Type: application/json

{
  "course_id": "curso-hackathon-001",
  "locale": "es",
  "api_key": "opcional-si-el-servidor-la-tiene",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "google/gemini-3-flash-preview",
  "content": {
    "course": {"title": "Curso de ejemplo"},
    "chunks": [{
      "id": "chunk-1",
      "title": "Primera lección",
      "theme": "sci-fi",
      "content": "Contenido educativo"
    }]
  }
}
```

Respuesta inmediata:

```json
{"job_id":"a1b2c3d4e5","course_id":"curso-hackathon-001"}
```

Consultar `/api/jobs/a1b2c3d4e5` hasta `completed` o `failed` y abrir:

```text
/play?course=curso-hackathon-001&game=chunk-1
```

---

## 11. Configuración

El servidor busca `.env` en el directorio actual, la raíz del repositorio y el paquete, en ese orden.

```env
API_KEY=tu-clave
API_BASE_URL=https://openrouter.ai/api/v1
MODEL=google/gemini-3-flash-preview
```

| Variable | Default | Uso |
|---|---|---|
| `API_KEY` | vacío | Clave de IA. |
| `OPENROUTER_API_KEY` | vacío | Alias de clave. |
| `OPENROUTER_API_KEY_studio` | vacío | Alias heredado. |
| `API_BASE_URL` | OpenRouter `/api/v1` | Base compatible con OpenAI. |
| `STUDIO_AI_BASE_URL` | vacío | Alias de base URL. |
| `MODEL` | `google/gemini-3-flash-preview` | Modelo global. |
| `STUDIO_MODEL` | vacío | Alias del modelo. |
| `STUDIO_MODEL_<ETAPA>` | modelo global | Modelo por etapa. |
| `BIND_HOST` | `127.0.0.1` | Host de `start.sh`. |
| `PORT` | `8000` | Puerto principal. |
| `MINDCRAFTED_HOME` | raíz repo/CWD | Raíz de datos mutables. |
| `ENGINE_STATE_URL` | `http://127.0.0.1:3100` | Servicio Node. |
| `MINDCRAFTED_ENGINE_STATE_AUTO` | `1` | Autoarranque Node. |
| `NODE_BINARY` | detectado | Node para el validador. |
| `GAME_PACKAGE_SECRET` | vacío | Secreto de cifrado. |
| `OBFS_JS` | apagado | Minificación con Terser. |

No versionar `.env` ni imprimir su contenido.

---

## 12. Ejecución

El entorno recomendado es `mindcrafted_V2/`, creado para esta ejecución. `mindcrafted_V1/` es el entorno anterior y ambos están excluidos de Git.

```bash
source mindcrafted_V2/bin/activate
export PYTHONPATH="$PWD"
uvicorn edgameclaw.server:app --reload --host 127.0.0.1 --port 8000
```

Abrir `http://127.0.0.1:8000/studio`.

Después de activar el entorno también se puede usar:

```bash
./start.sh
```

Advertencia: `start.sh` mata forzosamente cualquier proceso en el puerto `3100`, inicia Node y luego Uvicorn. No usarlo sin modificar en un entorno compartido.

### Entorno limpio

Este snapshot no contiene un archivo reproducible de dependencias (`pyproject.toml`, `setup.py` o `requirements.txt`). Para reconstruir el entorno manualmente:

```bash
python3 -m venv mindcrafted_V2
source mindcrafted_V2/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  'fastapi>=0.100.0' 'uvicorn[standard]>=0.22.0' \
  'python-multipart>=0.0.6' 'aiofiles>=23.0.0' \
  'httpx>=0.24.0' 'python-dotenv>=1.0.0' \
  'openai>=1.0.0' 'esprima>=4.0.1' 'jinja2>=3.1.0'
export PYTHONPATH="$PWD"
uvicorn edgameclaw.server:app --reload --host 127.0.0.1 --port 8000
```

Node manual:

```bash
cd mindcrafted/node
PORT=3100 node server.js
```

---

## 13. Idiomas y temas

Idiomas: `es`, `en`, `zh`, `ja`, `fr`, `ko`, `ar`, `de`.

Temas:

```text
pink-cute ocean-dream forest-sage sunset-warm galaxy-purple candy-pop
retro-amber china-porcelain china-cinnabar china-ink dunhuang forbidden-red
china-landscape china-rouge renaissance baroque nordic victorian mediterranean
fairy-tale detective sci-fi academy myth
```

Defaults: idioma `es`, tema `pink-cute`, audio `retro`.

---

## 14. Integración con otro proyecto

### Recomendación para la hackathon

Mantener dos servicios:

```text
Proyecto principal
├── autenticación y usuarios
├── base de datos
├── experiencia principal
└── cliente HTTP de MindCrafted

MindCrafted
├── parsing educativo
├── generación con IA
├── almacenamiento de artefactos
└── reproductor
```

Flujo recomendado:

1. El backend principal autentica al usuario.
2. Construye el JSON `content` o usa el endpoint de Markdown.
3. Llama a `POST /api/generate` desde servidor a servidor.
4. Guarda la relación entre su ID y `course_id`.
5. Consulta el job hasta terminar.
6. Lee el manifiesto.
7. Muestra `/play?...` directamente o dentro de un `iframe`.

```html
<iframe
  src="http://localhost:8000/play?course=curso-hackathon-001&game=chunk-1"
  title="Juego educativo"
  allow="autoplay; fullscreen">
</iframe>
```

Mantener la clave de IA en el backend principal o en el `.env` de MindCrafted. No enviarla al navegador en un despliegue público.

### Host recomendado

Es más sencillo asignar un origen propio:

```text
app.hackathon.test    -> proyecto principal
games.hackathon.test  -> MindCrafted
```

Usar un subpath como `/mindcrafted` requiere modificar rutas absolutas `/api`, `/assets`, `/engine`, `/courses` y `/play` en fuentes y artefactos generados.

### Mismo proceso FastAPI

Se puede importar `mindcrafted.server:app`, pero montarlo como subaplicación no es inmediato por las rutas absolutas. Antes se necesita:

- una configuración `BASE_PATH`;
- construcción centralizada de URLs;
- adaptar `StaticFiles`;
- adaptar URLs inyectadas en paquetes;
- adaptar links y redirects de los HTML.

### Persistencia futura

Para multiusuario reemplazar:

- `courses.json` por tabla `courses`;
- `jobs/*.json` por tabla/cola;
- `courses/<id>` por object storage;
- `asyncio.create_task` por worker persistente;
- eliminación directa por operación autorizada/auditable.

### Autorización futura

Opciones:

- ocultar MindCrafted detrás del backend principal;
- validar JWT con dependencias de FastAPI;
- usar token de servicio entre backends;
- entregar paquetes mediante URLs firmadas.

No tratar los hooks `auth` y `authUI` del frontend como seguridad real.

### Checklist de integración

- [ ] Definir IDs únicos y estables.
- [ ] Mantener la API key en servidor.
- [ ] Limitar tamaño y cantidad de lecciones.
- [ ] Implementar o desactivar reportes de minijuegos.
- [ ] Proteger generación, listado y eliminación.
- [ ] Evitar dos jobs con el mismo `course_id`.
- [ ] Probar escritorio y móvil horizontal.
- [ ] Revisar exactitud pedagógica.
- [ ] Revisar AGPL-3.0 con la licencia del otro proyecto.

---

## 15. Estado real, limitaciones y riesgos

### Incompatibilidades críticas

1. **Reporte ausente:** `engine.js` hace POST a `/api/report-minigame-error`, ruta no definida.
2. **Fuente ausente:** se referencia `/assets/ZhengQingKeNanBeiCiGongPuSongTi-2.ttf`, no presente en `assets/`.

### Seguridad y operación

3. CORS permite cualquier origen, método y header.
4. No hay autenticación de servidor; se puede listar, generar y borrar si la red permite acceso.
5. El Studio guarda opcionalmente la API key en `localStorage`.
6. `game.pkg.json` contiene JS generado que el player inyecta y ejecuta.
7. El sandbox es un validador con DOM simulado, no una frontera de seguridad fuerte.
8. Los jobs usan `asyncio.create_task`; un reinicio detiene la tarea.
9. Los snapshots excluyen logs, así que el detalle se pierde tras reiniciar.
10. `DELETE` usa `shutil.rmtree()` sin recuperación.
11. Dos jobs con el mismo curso pueden colisionar.
12. `start.sh` mata cualquier proceso en `3100`.

### Heredado o experimental

13. Node se inicia y tiene proxies, pero el player procesa el guion en navegador y no usa `/state`/`next`.
14. Se puede crear `game.pkg.enc`, pero el servidor de reproducción solo lee `game.pkg.json`.
15. `cryptography` no está en dependencias principales.
16. `npx terser` puede necesitar red y agregar latencia.
17. Se recopila usage de tokens en contexto, pero no se devuelve en la API.
18. No hay tests funcionales; las workflows solo construyen/publican.
19. Los HTML grandes y rutas absolutas dificultan montar bajo un prefijo.

Prioridad para hackathon: proteger generación/eliminación, implementar o retirar reportes y añadir límites/tests mínimos.

---

## 16. Seguridad, privacidad y licencia

- `.env` está ignorado por Git.
- `/api/config` informa si existe una clave, pero no la devuelve.
- Usar HTTPS en despliegue.
- No registrar bodies con `api_key`.
- Revisar manualmente contenido educativo generado.
- Considerar CSP e `iframe sandbox` para contenido de usuarios.
- No ejecutar paquetes generados de una fuente no confiable sin más aislamiento.

El código usa AGPL-3.0-or-later. Integrarlo y ofrecerlo por red puede implicar obligaciones de compartir el código fuente correspondiente. Revisar `LICENSE` y compatibilidad con el otro proyecto. Esto no es asesoramiento legal.

---

## 17. Pruebas recomendadas

Agregar:

1. unit test de `parse_markdown()`;
2. test de IDs/traversal;
3. test de registro de cursos con directorio temporal;
4. test de generación con cliente IA mockeado;
5. test de reanudación por checkpoint;
6. JSON Schema para el paquete;
7. test browser Studio → job → player;
8. test de sintaxis JS;
9. test de links generados;
10. test de arranque limpio.

Revisión estática:

```bash
python -m compileall mindcrafted
node --check mindcrafted/engine/engine.js
node --check mindcrafted/node/server.js
node --check mindcrafted/node/engine-state.js
```

No llamar IA real en CI; usar fixtures para evitar costo y variabilidad.

---

## 18. Glosario

| Término | Significado |
|---|---|
| Curso | Colección creada desde un Markdown. |
| Chunk | Lección creada desde un `##`. |
| Juego | Experiencia producida para un chunk. |
| Capítulo | Subunidad narrativa dentro de un juego. |
| Simulación | Minijuego JS asociado a un capítulo. |
| Guion | Lista de fondos, capítulos, diálogos, minijuegos y final. |
| Package | JSON con configuración, guion, estilos y JS. |
| Manifest | Resumen del curso y cada generación. |
| Job | Proceso asíncrono identificado por 10 caracteres. |
| Checkpoint | Cache intermedia reutilizable. |
| Theme | Dirección visual de una lección. |
| Locale | Idioma de salida/interfaz. |
| BYOK | El usuario entrega su propia API key. |

---

## 19. Instrucciones para la próxima IA

1. Leer este archivo completo.
2. Tomar el código `mindcrafted/` como fuente de verdad.
3. Leer `server.py`, `course_pipeline.py` y `generate_game()`.
4. Identificar stack, auth, storage y despliegue del otro proyecto.
5. Preferir integración HTTP en la primera versión.
6. No asumir que auth, pagos, analítica o reportes heredados funcionan.
7. Implementar o retirar el endpoint de reporte de minijuegos.
8. Proteger generación y eliminación.
9. Usar IDs únicos.
10. Tratar el paquete como código activo.
11. Añadir dependencias reproducibles y tests antes de refactorizar el pipeline.
12. Conservar atribución y revisar AGPL.

Archivos fuente de verdad:

```text
mindcrafted/server.py
mindcrafted/generator/course_pipeline.py
mindcrafted/generator/pipeline.py
mindcrafted/generator/api.py
mindcrafted/generator/assembler.py
mindcrafted/engine/player.html
mindcrafted/engine/engine.js
```

---

## 20. Comandos rápidos

```bash
# Entorno local existente
source mindcrafted_V2/bin/activate
export PYTHONPATH="$PWD"

# Servidor
uvicorn edgameclaw.server:app --reload --host 127.0.0.1 --port 8000

# Node auxiliar
cd mindcrafted/node
PORT=3100 node server.js

# Salud de Node
curl http://127.0.0.1:3100/health

# Cursos
curl http://127.0.0.1:8000/api/courses
```

MindCrafted aporta a la hackathon la parte más costosa de **contenido educativo → experiencia jugable**. El proyecto que lo integre puede concentrarse en usuarios, datos, personalización, negocio y presentación final.
