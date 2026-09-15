# V2.1.2 — Model Bake-off

El comparador mide la fiabilidad inicial de generación de Blueprint. Reutiliza
`api.generate`, el schema canónico y los validadores existentes; no cambia
`node_connect`, el grounding, el solver ni el QualityGate.

```sh
.venv/bin/python -m mindcrafted.generator.model_bakeoff \
  --source output/reliable-ai/model-source-ab-20260914/source-b-neural-networks.txt \
  --output output/reliable-ai/model-bakeoff-NUEVA-EJECUCION \
  --models nvidia/nemotron-3-super-120b-a12b:free \
    nex-agi/nex-n2.5-pro:free dots-studio/dots-3-note-preview:free
```

Los IDs del ejemplo se verificaron el 15 de septiembre de 2026. El runner vuelve
a consultar el catálogo y los endpoints antes de llamar a los modelos. Requiere
3–6 IDs distintos del catálogo; excluye endpoints sin disponibilidad o sin los
parámetros necesarios. No usa el router `openrouter/free`. Las credenciales se
resuelven mediante el adaptador existente y no aparecen en los artefactos.

## Protocolo congelado antes de llamar

- Source B exacta, SHA256
  `222b25809d0e03f19174010d85a7b838b00f3bad3bb79aa04deae0efbcc70213`.
- Un mismo `WORLD_DESIGN_SYSTEM`, payload de usuario y schema para todos.
- Temperatura 0,2; `top_p=1`; razonamiento `medium`; 16.384 tokens de salida.
  No se fijó seed porque no todos los endpoints la admiten. Estos parámetros
  difieren del experimento histórico; sus resultados no se mezclan con esta ronda.
- `json_schema`, `strict=true`, `require_parameters=true`, comprobación local
  del wire schema y del schema canónico. No hay degradación automática de modo.
- Cinco probes por modelo, intercalados por repetición, con hasta dos solicitudes
  simultáneas por el semáforo del adaptador.
- Cero reparaciones semánticas en las rondas de selección. Hasta dos intentos
  técnicos por probe exclusivamente para fallos transitorios.
- Umbrales: respuesta ≥0,90; schema ≥0,90; semántica ≥0,80. Se comparan valores
  exactos, sin redondear. Con cinco probes esto requiere 5/5, 5/5 y 4/5.

El score auxiliar pondera semántica, schema, grounding y respuesta, penalizando
retries. No sustituye los umbrales. La selección ordena los modelos elegibles por
esos criterios, en ese orden. Hasta dos finalistas pasan a diez probes nuevos
con el mismo protocolo. Solo un modelo que aprueba también esa ronda puede
generar una campaña.

## Métricas y límites

`providerResponseRate` cuenta HTTP 200, incluyendo respuestas que luego fallan
JSON/schema; no significa respuesta útil. JSON, schema, semántica y grounding
son métricas distintas. Los errores del proveedor se cuentan por intento, incluso
cuando un retry posterior funciona.

El grounding resuelve las citas mediante los mismos spans literales utilizados
por el KnowledgeGraph del paquete. Un span demuestra procedencia textual; no
demuestra por sí mismo la verdad de una relación inferida. El probe semántico
reutiliza `validate_mechanics`. Solvabilidad, causalidad educativa profunda,
simulación, navegador y AI Judge pertenecen a la campaña posterior. Un modelo
seleccionado puede fallar esa campaña.

El denominador de las tasas es el número de probes planificados. Una ronda
incompleta nunca permite seleccionar un modelo. Un rate limit agotado detiene
la serie; un error permanente de acceso/contrato desactiva ese modelo sin
repetir solicitudes inútiles. Los probes no ejecutados no se presentan como
respuestas inválidas reales: se reportan como muestra incompleta.

El catálogo permite observar `structured_outputs`, pero no prueba garantías
strict del backend. `ModelProfile.supportsStrictSchema` permanece desconocido
hasta contar con evidencia adicional; los resultados locales de cada respuesta
quedan separados de esa declaración. No se compara un endpoint sin soporte como
si fuera equivalente a uno que sí lo anuncia.

## Repair y campaña, solo después de seleccionar

El ganador recibe hasta tres outputs propios reales que pasaron schema y fallaron
semántica, junto con sus diagnósticos. Se mide una reparación de contenido por
caso. No se inventan outputs inválidos si todas sus muestras eran válidas.

La campaña usa `generate_campaign` existente: schema → semántica → compilación
y solver → QualityGate determinista, incluida simulación/Playwright → AI Judge
real → publicación. El modelo no edita ni publica directamente el paquete.
La herramienta mantiene el mismo modelo durante este experimento; la API
existente conserva configuración por etapa para futuras comparaciones de roles.

`protocol.json`, perfiles, capacidades, solicitudes, respuestas, spans y eventos
se guardan bajo el directorio de salida. La herramienta rechaza sobrescribir una
ejecución y verifica el hash de `courses.json`. Los artefactos contienen material
educativo y salidas no confiables del modelo, nunca claves o headers.

Si se interrumpe la primera ronda, `--resume-round-one` conserva las muestras
completadas y solicita únicamente las observaciones pendientes. Comprueba antes
los hashes de fuente, prompt, schemas, validador, configuración, umbrales y lista
de modelos. Archiva las solicitudes sin resultado como `OUTCOME_UNOBSERVED`;
no inventa errores HTTP ni las cuenta como reparaciones semánticas. Vuelve a
comprobar disponibilidad y conserva ambos snapshots de capacidades. No permite
repetir una campaña, repair o segunda ronda ya iniciados mediante esa opción.

Los resultados medidos están en
[`reports/model-bakeoff.md`](../reports/model-bakeoff.md).

## Referencias de capacidades

- [Catálogo y supported_parameters de OpenRouter](https://openrouter.ai/docs/guides/overview/models)
- [Structured Outputs y require_parameters](https://openrouter.ai/docs/guides/features/structured-outputs)

La evidencia local del endpoint y las llamadas reales prevalecen sobre una
descripción comercial del modelo.
