# Validación de la entrega

Comprobada el 8 de septiembre de 2026.

- **Aseprite:** 26 originales con capas; ocho recursos animados; 26 paletas GPL. Exportación de los originales hacia PNG y hojas horizontales ejecutada correctamente.
- **Escenarios completos:** tres originales adicionales en `scenes/`, con objetos separados en capas. Sus PNG exportados por Aseprite coinciden píxel por píxel con los renderizados de Tiled (RGBA, 768 × 512).
- **Tiled 1.12.2:** los tres mapas `.tmj` se abrieron mediante exportación CLI a `.tmx`; el renderizador nativo produjo las tres vistas PNG sin errores.
- **Integridad:** tamaños PNG, cabeceras y fotogramas Aseprite, referencias de tilesets, IDs únicos, punto inicial libre e interacciones accesibles comprobados por `check_assets.py`.
- **Modelos:** circuito abierto/cerrado, rechazo de resistencia cero, conservación de la solución de una ecuación y comportamiento de los factores limitantes comprobados por `check_models.mjs`.
- **Chromium:** carga de los tres mundos, cambio de parámetros, resolución de los tres objetivos, apertura/cierre de notas, escritorio 1440 × 1250 y móvil 390 × 844. No se detectaron excepciones JavaScript ni respuestas HTTP con error durante la prueba.
- **Accesibilidad comprobada:** alternativa de botones a los puntos del Canvas, ausencia de desbordamiento horizontal en móvil y reacción a cambios de la preferencia de movimiento reducido. Esto no constituye una auditoría completa de accesibilidad.

## Alcance

Las pruebas descritas arriba corresponden a la biblioteca y su demostración independiente, cuyas actividades son fijas. La integración posterior con apuntes, planes de puzzles y cursos se documenta en [GUIA_GENERADOR_PUZZLES.mk](../../GUIA_GENERADOR_PUZZLES.mk), junto con sus pruebas específicas. El bosque de la demostración utiliza un modelo conceptual explícitamente simplificado.

Las capturas están en `previews/atlas-desktop.png`, `previews/atlas-biology.png` y `previews/atlas-mobile.png`.
