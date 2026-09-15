# V2.1.1 — Reliable AI Generation

La comparación posterior de modelos con Source B se ejecuta mediante el
[protocolo V2.1.2 Model Bake-off](MODEL_BAKEOFF.md), con umbrales propios fijados
antes de medir y sin reparaciones de contenido durante la selección.

`AI DESIGNS — CODE DECIDES` sigue siendo el contrato. Esta fase modifica la
frontera con el proveedor y su diagnóstico; no modifica el solver, el runtime,
la validación educativa ni los umbrales del QualityGate de `node_connect`.

## Arquitectura

```text
Proveedor compatible con Chat Completions
  → api.generate_response
  → NormalizedModelResponse
  → JSON estricto y schema de respuesta
  → schema canónico y validación semántica
  → compilador / solver
  → QualityGate determinista (incluye simulación y navegador)
  → AI Judge real
  → paquete publicable
```

`api.generate()` conserva la interfaz de texto compartida con V1. Las diferencias
entre respuestas de SDK y envelopes JSON se resuelven en `provider_response.py`.
El contenido de razonamiento y las llamadas a herramientas no se interpretan como
Blueprints. No se ejecuta código generado. El parser V2 rechaza Markdown, JSON
truncado, claves duplicadas, números no finitos y envelopes incorrectos; no los
corrige silenciosamente. El argumento histórico `parse_json` del pipeline se
conserva por compatibilidad, pero V2 utiliza el parser estricto.

## Una fuente de schema

La fuente es el modelo Pydantic de `world_schema.py`, del que ya se exportan los
schemas del runtime, incluido `node-connect.schema.json`. `structured_schema.py`
deriva el schema enviado a la API de `BLUEPRINT_SCHEMA`:

- Para la validación enfocada, conserva un puzzle `node_connect` y sus definiciones
  transitivas. No mantiene una segunda descripción manual del archetype.
- En modo strict convierte únicamente uniones discriminadas y disjuntas de
  `oneOf` a `anyOf`, y `const` a `enum` de un elemento.
- Exige los campos existentes y objetos cerrados, conservando patrones, límites,
  referencias y restricciones. El campo opcional canónico `role` debe enviarse
  explícitamente en la respuesta strict.
- Valida localmente tanto el contrato de respuesta como el canónico. Que un
  endpoint acepte el parámetro strict no demuestra que toda respuesta lo cumpla.

Se envía realmente `response_format.type = json_schema` con `strict = true`.
OpenRouter recibe además `provider.require_parameters = true`. No hay descenso
automático a JSON mode después de un error. Los modos alternativos `best_effort`
(`json_schema`, strict false) y `json_mode` deben seleccionarse explícitamente y
quedan registrados.

## Proveedor y modelo independientes

Para Groq, preparar en el entorno privado:

```dotenv
STUDIO_AI_PROVIDER=groq
GROQ_API_KEY=<configurar de forma privada>
STUDIO_MODEL=openai/gpt-oss-120b
```

No se reutiliza una clave de OpenRouter para Groq. Groq no se llamó en la
validación documentada porque no había `GROQ_API_KEY` disponible.

OpenRouter continúa admitido mediante `OPENROUTER_API_KEY`,
`OPENROUTER_API_KEY_studio` o el alias existente `API_KEY`. `API_BASE_URL` y
`STUDIO_AI_BASE_URL` siguen admitidos para endpoints compatibles. La selección
explícita `provider=groq` utiliza su URL aunque el entorno general esté configurado
para OpenRouter. Una URL explícita contradictoria con un proveedor conocido se
rechaza.

`openrouter/free` sigue disponible para desarrollo, pero la validación
`fixed_model=True` rechaza ese router, `openrouter/auto` y alias equivalentes. El
modelo explícito prevalece sobre overrides de etapa en esta validación; V1
conserva su precedencia histórica. Se comprueba el identificador devuelto por el
proveedor, permitiendo únicamente la diferencia del sufijo de precio `:free`.
Fijar un identificador no garantiza salidas idénticas ni congela futuras
actualizaciones de pesos del proveedor.

## Errores y límites de reintento

| Categoría | Tratamiento |
| --- | --- |
| `PROVIDER_TIMEOUT`, `PROVIDER_CONNECTION_ERROR` | Retry técnico acotado |
| `PROVIDER_EMPTY_RESPONSE` | Retry técnico; no usar razonamiento como respuesta |
| `PROVIDER_RATE_LIMIT` | Retry técnico con espera; detener la serie si se agota |
| `PROVIDER_UPSTREAM_ERROR` | Retry técnico para fallo temporal upstream |
| `PROVIDER_HTTP_ERROR` | Rechazar errores permanentes, incluidos 400/401/402/403 |
| `PROVIDER_REFUSAL` | Rechazar, sin retry ni intento de evitar la negativa |
| `PROVIDER_INVALID_RESPONSE`, `PROVIDER_MODEL_MISMATCH`, `PROVIDER_CONFIG_ERROR` | Rechazar el contrato/configuración de proveedor |
| `LLM_TRUNCATED_RESPONSE` | Repair de contenido, con diagnóstico de límite de salida |
| `LLM_JSON_PARSE_ERROR`, `LLM_INVALID_ENVELOPE`, `LLM_SCHEMA_ERROR` | Repair con candidato y diagnóstico |
| `SEMANTIC_VALIDATION_ERROR`, `REFERENCE_ERROR`, `UNSOLVABLE` | Repair de contenido, nunca retry de transporte |
| Errores educativos, de dificultad o integración | Repair; gate sin relajar |
| `DETERMINISTIC_GATE_FAILURE`, `AI_JUDGE_REJECTION` | Repair; no publicar |

El SDK tiene retries desactivados. El adaptador controla las repeticiones de la
misma solicitud: el pipeline permite como máximo **dos intentos de proveedor por
llamada**. El nombre histórico `max_retries` significa intentos totales. Hay una
espera acotada de 2 segundos por intento, o 10 segundos para 429, con máximo de 30.
No se espera después del último intento.

El pipeline permite **tres candidatos en total**: inicial y hasta dos reparaciones.
Cada reparación recibe el candidato anterior, categoría, etapa y diagnóstico.
Agotar los retries técnicos no activa el repair de contenido. Una truncación
requiere corregir o acortar la generación; no se repite ciegamente como si fuera
un error HTTP. El único fallback sigue siendo un paquete aprobado previamente,
del mismo material, revalidado. La herramienta de medición exige un directorio
nuevo para que ese fallback no contamine los resultados.

## Observabilidad y ejecución

Cada intento de proveedor registra generación, proveedor, modelo solicitado y
devuelto, etapa, intento, reparación, latencia, estado HTTP cuando existe, modo
estructurado, versión y hashes separados del schema canónico y del schema wire,
categoría de error y tokens reportados.
`response_status = ok` significa respuesta normalizada y, cuando se solicitó,
schema de respuesta válido; semántica y gates se registran por separado en la
traza del pipeline. Las primeras sondas se ejecutaron antes de mover el registro
de errores locales de JSON/schema al mismo evento de proveedor; sus trazas
conservan el diagnóstico de contenido por separado.
No se registran claves, headers de autorización ni mensajes crudos de excepciones
HTTP. El runner opt-in guarda el material, prompts y respuestas como evidencia
local: esos artefactos deben tratarse con la privacidad del material de entrada.

Ejemplo de prueba aislada con credencial Groq disponible:

```sh
.venv/bin/python -m mindcrafted.generator.world_ai_validation probe \
  --source ruta/material-real.txt --output output/groq-probe \
  --provider groq --model openai/gpt-oss-120b --probes 5
```

Después, la serie completa (incluye su propia prueba aislada):

```sh
.venv/bin/python -m mindcrafted.generator.world_ai_validation run \
  --source ruta/material-real.txt --output output/groq-series \
  --provider groq --model openai/gpt-oss-120b --probes 5 --runs 5
```

El modelo fijo gratuito probado por OpenRouter fue
`nvidia/nemotron-3-super-120b-a12b:free`. El parámetro opcional
`--reasoning-effort low` regula razonamiento sin cambiar schema ni gates. Se
excluye el razonamiento de la respuesta pública. También existen
`STUDIO_REASONING_EFFORT`, `STUDIO_STRUCTURED_OUTPUT` y `STUDIO_AI_TIMEOUT`.
El runner usa timeout de lectura de 120 segundos, configurable con `--timeout`;
no es un deadline total de pared si el proveedor mantiene actividad de red.

El preflight ejecuta varios probes y mide respuesta del proveedor, parseo/schema y
validación semántica. Un PASS en él **no aprueba el puzzle**. Por cada campaña se
conservan llamadas, traza, reparaciones y resultado.
Los porcentajes por ejecución significan que al menos un candidato alcanzó la
etapa dentro del presupuesto; no son tasas de éxito al primer intento. Los
probes se reportan aparte. La CLI sale con error si no hay paquete aprobado y no
modifica el registro real `courses.json`.

## Evidencia y referencias

Los resultados reales y sus límites se publican en
[`reports/reliable-ai-generation-ab.md`](../reports/reliable-ai-generation-ab.md).
No se infiere un AI Judge PASS de tests con dobles ni de un schema válido.

- [OpenAI: Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Groq: Structured Outputs y modelos strict](https://console.groq.com/docs/structured-outputs)
- [OpenRouter: Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenRouter: razonamiento y presupuesto de tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)

Las capacidades se comprobaron el 14 de septiembre de 2026; la disponibilidad y
los límites del endpoint pueden cambiar.
