# Dirección artística · Atlas 01

## Reglas comunes

- Perspectiva superior con caras frontales visibles; iluminación desde arriba a la izquierda.
- Rejilla de terreno de 32 × 32 px; mapas de 24 × 16 casillas (768 × 512 px).
- Los objetos pueden ocupar varias casillas. Su anclaje está en la esquina inferior izquierda; su coordenada Y determina el orden de dibujo.
- Píxeles enteros y bordes definidos. Las fuentes exportadas no llevan suavizado; el navegador puede superponer iluminación ambiental.
- Sombras coloreadas, contornos oscuros, brillos discretos y pequeñas texturas de material.
- Los diagramas de las pizarras evitan textos diminutos. Las explicaciones educativas se muestran como texto HTML legible.
- Las animaciones originales usan 160 ms por fotograma. El renderizador presenta el personaje en reposo; la secuencia de caminar queda preparada para un futuro controlador.

## Familias visuales

| Familia | Materiales | Paleta principal | Objetos que cuentan la materia |
|---|---|---|---|
| Física | Acero, cobre, vidrio | Azul profundo, turquesa, cobre y crema | Reactor, bobinas, baterías, instrumentos y lámparas |
| Matemáticas | Madera, papel, latón | Marrón violáceo, miel, verde pizarra y pergamino | Balanza, bloques, libros, diagramas y modelo orbital |
| Biología | Corteza, follaje, piedra, agua | Verde azulado, musgo, arena y rosa apagado | Colmena, flores, helechos, hongos y río |

## Contrato de los recursos

El catálogo distingue la imagen estática del primer fotograma y la hoja horizontal animada. Las hojas no se recortan: cada celda mide exactamente `width × height`. `frameDuration` está expresado en milisegundos. Cada asset_id es estable y también aparece en las propiedades de objetos Tiled.

La colección `tilesets/objects.tsj` utiliza PNG individuales para conservar el tamaño de cada objeto. Los atlas de terreno son imágenes de 256 × 64, con 16 piezas de 32 × 32. Los identificadores Tiled empiezan en 1 para terreno y 100 para objetos.

## Cómo añadir un recurso

1. Dibujar el original `.aseprite` con sus capas y una paleta de su familia.
2. Exportar PNG y, si está animado, su hoja horizontal.
3. Registrar ID, dimensiones, duración, fotogramas y rutas en ambos catálogos.
4. Añadir la entrada a `objects.tsj` con un ID local nuevo y estable.
5. Colocarlo en Tiled. Añadir su huella de colisión y punto interactivo por separado cuando corresponda.
6. Exportar el mapa y ejecutar las comprobaciones.

## Criterio de singularidad

Cambiar de paleta no define un juego nuevo. Cada mundo debe proponer acciones propias del concepto: conectar y medir; transformar cantidades manteniendo una igualdad; o intervenir sobre relaciones entre recursos y organismos. El recurso artístico debe comunicar esa acción.

Este primer atlas establece una base modular de pixel art. Su ampliación puede incorporar más poses, transiciones de terreno, interiores, variaciones estacionales y objetos específicos de nuevas lecciones. Los modelos científicos necesitan revisión pedagógica independiente de la validación técnica.
