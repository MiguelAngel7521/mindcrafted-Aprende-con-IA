# Propuesta: MindCrafted como aventura de aprendizaje

Estado: propuesta para revisión. Implementación pendiente de tu autorización.
Fecha: 8 de septiembre de 2026.
Carpeta analizada: mindcrafted/, con sus recursos en ../pixel_worlds/ y pruebas en ../tests/.

Este .mk contiene documentación, no instrucciones ejecutables ni un Makefile.
En esta revisión solo se crea este documento. No se modifica código, mapas,
sprites, cursos ni configuración. La guía existente describe la versión actual;
este archivo describe la experiencia que propongo construir después.

## 1. La experiencia que quiero construir

El estudiante entra en un pequeño mundo que representa sus apuntes. Puede
caminar, acercarse a objetos, investigar y activar retos. Resolverlos cambia
el escenario: se enciende un servidor, se abre una puerta, se repara una máquina
o se recupera una zona del bosque. Al terminar las lecciones disponibles,
aparece un jefe final que combina los conocimientos practicados.

La inspiración de Undertale estará en alternar exploración, diálogos breves
y combates de esquivar patrones dentro de una arena. MindCrafted tendrá sus
propios personajes, escenarios, efectos y reglas educativas. Las respuestas
formarán parte de la acción: llevar una señal al destino correcto, recoger
pasos en orden o activar una operación mientras se esquivan obstáculos.

La aventura debe pedir dos cosas distintas: entender el tema y controlar al
personaje. El ritmo se podrá ajustar sin cambiar qué conocimiento se practica.

Recorrido propuesto:

    Apuntes revisados → mundo temático → exploración e interacciones
        → retos de acción → cambios visibles en el mundo
        → siguiente lección → jefe final → resumen del aprendizaje

## 2. Qué encontré realmente en la carpeta

| Parte revisada | Estado actual | Ampliación necesaria |
| --- | --- | --- |
| generator/practice.py | Crea 3–5 puzzles, valida datos y evidencias, integra arte y mapa | Añadir dominio del tema, misiones, distribución del mundo y encuentros |
| engine/practice/runtime.js | Dibuja el mapa, anima un personaje fijo y abre ejercicios desde botones | Movimiento, colisiones, proximidad, exploración y estados de combate |
| engine/practice/player.html | Presenta un mapa junto a un panel de ejercicios | Vista de aventura y arena, con controles y objetivos contextuales |
| generator/course_pipeline.py | Genera lecciones y enlaza las que tuvieron éxito | Conectar etapas de la aventura y preparar el jefe final del curso |
| server.py | Sirve paquetes y elige el reproductor según el modo del juego | Reconocer el nuevo modo y entregar sus recursos |
| engine/bkt.js | Registra aciertos por concepto en el navegador | Recibir solamente resultados educativos, separados del daño de combate |
| ../pixel_worlds/ | Tres mundos, 26 originales Aseprite y mapas Tiled | Crear un cuarto mundo tecnológico y piezas para encuentros y jefes |

Observaciones que condicionan el diseño:

- Los mapas actuales tienen 24 × 16 tiles de 32 píxeles: cada sala mide 768 × 512.
- Ya existen las capas Suelo, Escenario, Interacciones, Colisiones e Inicio.
- El reproductor de práctica usa el suelo y los objetos visuales, pero no usa
  las colisiones ni el punto de inicio para mover al personaje.
- El personaje tiene ocho fotogramas y etiquetas idle/walk. Falta definir arte
  y animaciones para mirar y caminar en las cuatro direcciones.
- Actualmente la posición del personaje y la distribución de los marcadores
  están fijadas en el reproductor. No representan una exploración real.
- Las interacciones de Tiled tienen acciones y textos de demostración. Habrá
  que vincularlas a las misiones de cada lección, usando identificadores estables.
- Hay tres o cuatro interacciones por mapa, pero una lección admite hasta cinco
  puzzles. Se necesitarán nuevos puntos válidos o terminales con varias misiones.
- Tecnología comparte ahora el laboratorio; no tiene un mundo propio.
- El mundo se fuerza a matemáticas si aparece cierto puzzle numérico. Eso debe
  cambiar: un tema de programación puede usar números y seguir siendo tecnológico.
- El progreso actual finaliza al resolver los puzzles. No hay una batalla final.
- La biblioteca incluye una comprobación de accesibilidad sobre una rejilla de
  puntos. Habrá que verificar también que quepa la caja de colisión del personaje.

Estas conclusiones proceden de leer los archivos y examinar el laboratorio.
No he ejecutado ni modificado el juego durante este análisis.

## 3. Mundos según el contenido

Propongo añadir Nexo Digital, un centro tecnológico que reutilice la dirección
visual del laboratorio y tenga una composición propia. Será el entorno principal
para programación, redes, bases de datos, informática e inteligencia artificial.

| Contenido dominante | Mundo propuesto | Objetos que dan sentido a la práctica |
| --- | --- | --- |
| Programación, redes, datos y sistemas | Nexo Digital, nuevo | Servidores, terminales, nodos, routers, drones y puertas electrónicas |
| Física, electricidad y química | Laboratorio existente | Instrumentos, reactor, circuitos y estaciones de medida |
| Matemáticas y lógica matemática | Taller del equilibrio existente | Balanza, pizarra, mecanismos y biblioteca |
| Biología y ecología | Bosque existente | Plantas, colmena, organismos y recursos del entorno |
| Historia, lenguaje y otras materias | Aula/biblioteca existente como base | Archivos, libros y paneles de relaciones o cronologías |

El generador considerará los apuntes y la materia indicada. El estudio mostrará
el mundo elegido y permitirá cambiarlo antes de generar. En temas técnicos
ambiguos priorizaré Nexo Digital; biología o matemáticas explícitas conservarán
su identidad. La selección visual y la selección de mecánicas serán decisiones
separadas: un circuito puede ser parte de una lección tecnológica.

Nexo Digital incluirá una entrada segura, un corredor central, estaciones de
trabajo y una cámara final. Su aspecto tendrá metal oscuro, luces cian y ámbar,
cableado, pantallas animadas y maquinaria con estados apagado/activo/reparado.

## 4. Cómo se generará un mundo diferente

La base serán los escenarios y piezas editables de Aseprite/Tiled. Sobre esa
base se compondrá una aventura por lección:

1. Seleccionar el mundo y una distribución de sala compatible.
2. Asociar los conceptos de los apuntes con objetos y misiones concretas.
3. Distribuir estaciones, decoración y puertas en lugares permitidos.
4. Elegir variantes visuales, nombres, diálogos y patrones de encuentro.
5. Comprobar que desde Inicio se llega a las misiones y a la salida.
6. Guardar esa distribución y una semilla aleatoria dentro del paquete.

La semilla identifica la variación de esa partida: al recargar se conserva el
mismo mundo; al crear otra aventura puede cambiar. El azar tendrá límites para
evitar puertas inaccesibles, obstáculos encima del jugador o retos sin solución.
Si una distribución no es válida, se usará una distribución base comprobada.

La primera versión variará misiones, objetos, estados y encuentros dentro de
salas de tamaño controlado. Será posible ampliar después a varias salas, sin
prometer desde el principio un mapa gigantesco generado libremente.

Cada escenario seguirá siendo editable. Los sprites nuevos se crearán con
Aseprite y los mapas con Tiled, usando el flujo local y terminal existente,
sin MCP. Un jefe nuevo se compondrá a partir de piezas originales compatibles;
no hará falta dibujar todo su arte durante cada llamada al generador.

## 5. Movimiento e interacción

En escritorio, WASD o flechas moverán al personaje; E o Enter permitirán
interactuar; Escape abrirá la pausa. En móvil habrá una cruceta o control
direccional táctil y un botón de interacción.

El movimiento incluirá animaciones direccionales, velocidad consistente y una
caja de colisión en los pies. Árboles, máquinas, paredes y agua impedirán el
paso según las capas del mapa. El orden de dibujo permitirá pasar por delante
o por detrás de objetos altos de forma coherente.

Al acercarse a un elemento aparecerá una indicación, por ejemplo «E · Revisar
servidor». Un terminal podrá mostrar una pista, abrir una misión o informar de
un objetivo ya resuelto. Los textos largos se leerán con la acción detenida.

Completar un reto tendrá una consecuencia visible: conexiones iluminadas,
una puerta abierta o una máquina restaurada. El mapa mostrará qué falta para
avanzar. La posición, las misiones y las puertas se guardarán en el navegador.

La pausa y la pérdida de foco detendrán la acción y limpiarán las teclas
pulsadas para evitar movimiento involuntario al volver a la pestaña.

## 6. Puzzles de acción con respuestas dentro del juego

Cada encuentro tendrá una preparación breve para leer, una fase de acción
y una resolución con explicación. Como punto de partida, propondré rondas
de acción de unos 8–15 segundos, ajustables después de probar su dificultad.
El tiempo de lectura no consumirá esa ventana.

Las respuestas aparecerán como objetos, zonas, conexiones o recursos con los
que interactuar. Acercarse y confirmar, transportar o activar tendrá prioridad
sobre responder accidentalmente al rozar algo.

| Reto | Qué hace el jugador | Qué conocimiento decide el resultado |
| --- | --- | --- |
| Enrutamiento de señales | Lleva un paquete entre nodos y evita interferencias | Escoge el destino o recorrido válido según las reglas de los apuntes |
| Reconstrucción de procesos | Recoge y coloca etapas mientras aparecen obstáculos | Construye una secuencia con orden justificable |
| Rastreo de un algoritmo | Activa bloques y recoge estados o resultados en una arena | Predice cambios de variables o el resultado de un algoritmo acotado |
| Conexiones de conceptos | Transporta una señal entre dos estaciones | Relaciona correctamente concepto, función o consecuencia |
| Equilibrio de ecuaciones | Activa operaciones en ambos lados de una máquina | Conserva la igualdad y termina aislando la incógnita |
| Carga de fracciones | Recoge unidades iguales y descarga una cantidad en un receptor | Representa exactamente la fracción solicitada |
| Circuito bajo presión | Ajusta energía en estaciones y evita descargas señalizadas | Alcanza el objetivo respetando la regla eléctrica estudiada |
| Decisión con evidencia | Se desplaza hasta una zona y confirma una respuesta | Aplica lo aprendido a una situación concreta |

Las seis familias actuales aportan reglas que se pueden reutilizar. Enrutamiento
y rastreo de algoritmos necesitarán nuevas reglas y validadores. Empezaré con
casos acotados, tablas de estados y recorridos comprobables; el generador no
necesitará ejecutar programas arbitrarios enviados en los apuntes.

Solo se ofrecerá una mecánica si el material aporta lo necesario. Por ejemplo,
una lección de redes no tendrá que enseñar la ley de Ohm para poder generar
una aventura, y un tema histórico no se convertirá en un ejercicio de álgebra.

Los patrones de obstáculos tendrán aviso previo, espacio para esquivar y una
cantidad limitada de proyectiles. Las zonas de respuesta deben permanecer
alcanzables durante el tiempo necesario para decidir y actuar.

## 7. Jefe final aleatorio y relacionado con el tema

Propuesta inicial: un jefe final por curso, desbloqueado después de completar
las misiones requeridas de sus lecciones disponibles. Un curso de una sola
lección también tendrá su jefe al final de ese mundo.

Su diseño se compondrá con una familia visual, piezas, paleta y animaciones.
El nombre y el contexto reflejarán el tema. Ejemplos propuestos:

- Tecnología: un centinela de red, una entidad de datos o un núcleo de máquinas.
- Matemáticas: un guardián de mecanismos y equilibrio.
- Biología: un guardián del ecosistema construido con piezas del bosque.
- Laboratorio: un autómata de energía y medición.

La batalla tendrá tres fases iniciales. Cada fase planteará un reto derivado
de conceptos ya practicados, alternará acción y decisión y terminará con una
explicación breve. Una solución correcta quitará un segmento del escudo del
jefe; completar los tres segmentos permitirá vencerlo.

Esquivar servirá para sobrevivir. El conocimiento será lo que permita superar
las fases. El daño recibido no cambiará retroactivamente una respuesta correcta.
Al perder, se podrá reintentar la batalla sin perder las lecciones completadas.

El azar elegirá apariencia y patrones entre combinaciones válidas. Las respuestas
correctas dependerán del contenido. La semilla del jefe se guardará para que no
cambie de forma arbitraria al recargar o reintentar.

El jefe se preparará después de conocer qué lecciones se generaron. Si alguna
falló, el cierre cubrirá únicamente la parte disponible y lo indicará; no se
marcará como aprendido contenido ausente. Si el plan del jefe no pasa sus
validaciones, las lecciones seguirán disponibles y el cierre quedará pendiente,
con un error que permita reintentarlo.

## 8. Ejemplo de una partida tecnológica

Supongamos que los apuntes explican direcciones, rutas y entrega de paquetes.
El estudiante aparece en Nexo Digital y recibe una misión: restaurar la conexión
entre varias estaciones.

Se acerca a una consola, consulta las reglas y entra en una arena. Transporta
una señal al destino adecuado mientras esquiva interferencias. Después ordena
las etapas del proceso explicado en sus apuntes. Cada acierto restaura una
parte del centro y permite llegar a otra estación.

Al completar las lecciones, se abre la cámara del jefe. Un centinela generado
para esa aventura mezcla las relaciones y procesos ya practicados en tres fases.
Superarlo devuelve un resumen de los conceptos acertados y de los que conviene
repasar. Si los apuntes tratan otro tema, las misiones cambian con ese contenido.

## 9. Aprendizaje, dificultad y accesibilidad

Registraré por separado las respuestas conceptuales y el desempeño de acción.
BKT recibirá aciertos y errores educativos deliberados. Chocar con un proyectil,
agotarse el tiempo o moverse despacio no contará como desconocer la materia.

Habrá un ritmo normal, uno tranquilo y una opción de práctica sin presión de
combate. La ayuda podrá reducir velocidad y cantidad de obstáculos, ampliar
ventanas de respuesta y permitir reintentos. Las reglas educativas se mantendrán.

Se conservarán las pistas, los fragmentos de apuntes y las explicaciones. Las
respuestas se distinguirán mediante texto y forma además del color. Se incluirán
pausa, control táctil, efectos ajustables y reducción de movimiento visual.

El guardado seguirá siendo local en esta etapa: navegador y dispositivo actuales.
Añadirá posición, misiones, cambios del escenario, semilla y estado del jefe.
Cambiar de dispositivo no sincronizará la partida hasta incorporar cuentas y
persistencia en servidor, una ampliación separada.

## 10. Organización de la implementación propuesta

Mantendré el servidor y el generador actuales como base. El nuevo reproductor
usará Canvas y controles HTML donde faciliten lectura y accesibilidad. Separaré
exploración, reglas de encuentros y presentación para poder probarlas por partes.

Estas rutas son propuestas; todavía no se crean:

| Ruta propuesta o existente | Responsabilidad futura |
| --- | --- |
| engine/adventure/ | Reproductor de aventura, movimiento, colisiones, interacciones, arenas y guardado |
| generator/adventure.py | Composición de misiones, salas y encuentros a partir de contenido validado |
| generator/boss.py | Selección, composición y validación del jefe final |
| generator/practice.py | Conservar validación educativa y ampliar las familias admitidas |
| generator/course_pipeline.py | Preparar el cierre del curso y sus vínculos tras generar las lecciones |
| static/studio.html | Mostrar mundo, estilo de juego y estado de generación de aventura/jefe |
| server.py | Servir el nuevo modo y mantener acceso a paquetes anteriores |
| ../pixel_worlds/art/source/ | Nuevos originales tecnológicos, animaciones direccionales y piezas de jefes |
| ../pixel_worlds/maps/ y ../pixel_worlds/tilesets/ | Mapas y atlas nuevos, con interacciones y colisiones |
| ../pixel_worlds/manifest.json y scripts/ | Registrar y exportar los nuevos recursos |
| ../tests/ | Pruebas del generador, exploración, combate y recorrido completo |

El paquete de aventura incorporará una versión explícita, dominio de la lección,
identificadores de misiones, vínculos a objetos del mapa, semilla, reglas de
encuentros y referencias al cierre del curso. El plan del jefe incluirá los
conceptos y lecciones de origen de cada fase.

La IA propondrá datos y narrativa. El motor local controlará movimiento, daño,
patrones y validación de respuestas. Se comprobarán textos, rangos, referencias,
soluciones y rutas antes de publicar un paquete como listo.

Los cursos anteriores conservarán su reproductor. Las aventuras nuevas tendrán
su propio modo; una actualización del arte no sustituirá las copias ya integradas
en paquetes antiguos. La incorporación se hará sin regenerar los dibujos actuales
ni sobrescribir cursos como parte de una prueba.

## 11. Orden de trabajo cuando autorices el código

| Etapa | Entrega revisable | Cómo comprobaré que funciona |
| --- | --- | --- |
| 1. Exploración | Personaje controlable en los mapas existentes, colisiones e interacción cercana | Caminar, detenerse ante objetos, interactuar y reanudar después de una pausa |
| 2. Identidad tecnológica | Nexo Digital y arte direccional, con estaciones y estados visuales | Recorrer todas las estaciones sin quedar bloqueado y exportar desde Aseprite/Tiled |
| 3. Primer encuentro completo | Una misión de redes con lectura, arena, respuesta física y explicación | Resolverla por la ruta válida, fallar de forma controlada y conservar su efecto en el mundo |
| 4. Familias de retos | Adaptar las seis familias actuales y añadir las dos tecnológicas acotadas | Verificar soluciones y que el reto corresponda al contenido |
| 5. Generación de aventura | Apuntes → selección del mundo → misiones → paquete navegable | Generar materiales de temas distintos y comparar su contenido y sus interacciones |
| 6. Jefe final | Jefe compuesto, tres fases, victoria, derrota y reintento | Desbloqueo correcto, preguntas fundamentadas, patrones válidos y persistencia |
| 7. Cierre y pulido | Móvil, dificultad, guardado, documentación y pruebas completas | Completar una aventura desde la subida de apuntes hasta el resumen final |

La etapa 3 será una muestra pequeña pero completa para comprobar la sensación
de juego. Después se extenderá ese diseño a las demás mecánicas y materias.
Esa muestra será un hito de revisión, no el final del alcance propuesto.

## 12. Criterios para dar por terminada la mejora

- El personaje se mueve con teclado y controles táctiles, respeta obstáculos
  y se dibuja correctamente delante y detrás del escenario.
- Las misiones se activan por interacción con objetos y tienen efectos visibles.
- El mundo tecnológico existe y los otros escenarios siguen siendo seleccionables.
- El generador elige contenido y mecánicas según los apuntes; cada reto conserva
  una evidencia y una explicación. La cita literal por sí sola no se considera
  prueba suficiente de que una respuesta conceptual sea correcta.
- Los puzzles requieren actuar sobre respuestas dentro del juego y permiten
  completarse con las reglas indicadas, también con ayudas de dificultad.
- El jefe depende de conceptos practicados, puede vencerse y puede reintentarse.
- Una partida recargada conserva avances y semilla; un paquete diferente no
  hereda por error el progreso del anterior.
- Pausar o cambiar de pestaña no deja proyectiles ni teclas avanzando a escondidas.
- Los errores de generación y el contenido parcial se muestran con claridad.
- Se conservan los cursos anteriores y se comprueba tanto la carga desde la API
  como el paquete exportado y la navegación entre lecciones.

Las pruebas incluirán respuestas incorrectas, derrota y recuperación, separación
entre daño y aprendizaje, alcance real de interacciones y tiempos de simulación
consistentes en distintas velocidades de pantalla. Se ampliarán las pruebas
existentes y se verificará una partida real en navegador.

## 13. Límites y decisiones abiertas a tu revisión

La propuesta inicial es una aventura de salas compactas con un jefe final por
curso. La personalización combinará contenido de los apuntes, piezas originales,
distribuciones válidas y patrones controlados. Un mundo abierto extenso, sprites
enteramente inéditos en cada generación y multijugador serían fases posteriores.

Los intervalos de combate y las tres fases del jefe son valores iniciales de
diseño; se ajustarán según las pruebas de jugabilidad. La calidad educativa de
las respuestas del proveedor de IA también tendrá que revisarse con apuntes
reales, además de las pruebas con respuestas simuladas.

Este documento no autoriza ni inicia la implementación. El siguiente paso será
tu revisión y tu indicación expresa de cuándo comenzar a escribir código.
