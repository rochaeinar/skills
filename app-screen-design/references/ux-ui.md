# Reglas de UI/UX

Estilo: **moderno, limpio y minimalista**, al nivel de las mejores apps de su categoría. Pocas cosas por pantalla, jerarquía clara, mucho aire, un color de acento usado con intención, profundidad sutil.

## Principios
- **Una acción principal por pantalla** (botón lleno o FAB); las secundarias, más discretas. Las destructivas, en rojo y con confirmación o deshacer.
- **Jerarquía:** un título claro, luego el contenido; agrupar con espacio antes que con líneas y bordes.
- **Consistencia:** lo mismo se ve y se llama igual en toda la app. Un solo set de íconos (Material Symbols Rounded u Outlined, uno).
- **Deshacer antes que confirmar** para acciones reversibles (snackbar "Deshacer"); diálogo de confirmación solo para lo irreversible.
- **Divulgación progresiva:** lo avanzado en un sheet, una pantalla de detalle o "Más opciones".
- **Feedback inmediato:** cada toque tiene respuesta (ripple, estado presionado, progreso si tarda > 300 ms, resultado).
- **Errores útiles:** qué pasó y qué hacer, en lenguaje humano, con la acción para resolverlo. Nunca códigos crudos.
- **Estados vacíos que invitan:** ilustración o ícono simple, una frase y la acción para empezar.
- **Permisos con contexto:** explicar el porqué antes del diálogo del sistema; y una pantalla para "permiso denegado" con el camino a Ajustes.
- **Navegación (Android):** barra inferior con 3-5 destinos en teléfono; rail de navegación en tablet/horizontal; drawer solo si hay muchos destinos. Botón y gesto "atrás" predecibles. En iOS: tab bar y navegación con stack.

## Material 3 (Android)
- Roles de color: primary, onPrimary, primaryContainer, secondary, tertiary, surface y sus contenedores (surfaceContainerLow…High), outline, error. Colores dinámicos (Material You) como opción si se aprueba, con la paleta de marca como base.
- Escala tipográfica M3 (display, headline, title, body, label). Tamaño mínimo de cuerpo 14 sp; nunca menos de 12 sp.
- Rejilla de 4 dp; márgenes laterales 16 dp en teléfono, 24 dp en tablet.
- Formas: esquinas consistentes por tamaño de componente (pequeño 8, mediano 12, grande 16-28).
- Edge-to-edge (Android 15+): contenido detrás de las barras del sistema, con insets respetados.

## Tamaños de pantalla
| Ventana | Ancho | Diseño |
|---|---|---|
| Compacta | < 600 dp (teléfono vertical) | 1 columna, barra inferior |
| Media | 600-839 dp (tablet vertical, plegable) | rail de navegación, 2 columnas o lista+detalle según el contenido |
| Expandida | ≥ 840 dp (tablet horizontal) | rail o drawer fijo, lista+detalle, rejillas; ancho de lectura máx. ~ 640 dp |
| Teléfono horizontal | poca altura | rail en vez de barra inferior, cabeceras compactas, nada importante fuera de pantalla sin scroll, el teclado no tapa el campo |

Tamaños de cuadro de referencia: teléfono 360×800 dp (y 412×915), horizontal 800×360, tablet 800×1280 y 1280×800.

## Tema claro y oscuro
- El oscuro no es el claro invertido: superficies gris muy oscuro (no negro puro, salvo que se pida AMOLED), elevación con superficies más claras, colores de acento desaturados para no vibrar.
- Contraste mínimo WCAG AA en los dos: texto 4.5:1, texto grande e íconos 3:1. Verificarlo con los valores reales de los tokens.
- Imágenes e ilustraciones con versión para cada tema si hace falta.

## Accesibilidad
- Áreas táctiles ≥ 48×48 dp (aunque el ícono sea de 24).
- Funciona con fuente al 200 %: mostrar una pantalla clave con fuente grande.
- Nunca solo el color para comunicar (agregar ícono o texto).
- Cada ícono interactivo con descripción para TalkBack; orden de foco lógico; anotar ambos en el diseño.
- Movimiento reducido: las animaciones son decorativas y se pueden quitar.

## Movimiento
- Duraciones: 100-200 ms en micro interacciones, 250-400 ms en transiciones de pantalla. Curvas "emphasized" de M3.
- Transiciones con sentido: contenedor que se expande (lista → detalle), compartido entre ejes (pestañas), desvanecido (cambios sin relación).

## Cómo dibujar los comportamientos
- Cada comportamiento en su propio cuadro, en secuencia y numerado: **disparador** (dedo/flecha sobre el elemento, con la etiqueta "Toca", "Mantén presionado", "Desliza a la izquierda") → **comportamiento** (el diálogo, sheet, menú abierto sobre la pantalla atenuada) → **resultado** (la pantalla después, con el snackbar si lo hay).
- Deslizables: tres cuadros (reposo, a medio deslizar con la acción revelada, resultado).
- Bottom sheets: parcialmente expandido y expandido si los dos existen.
- Formularios: vacío, con foco y teclado, con error de validación, enviando, éxito.
- Si la herramienta lo permite, además un prototipo navegable del flujo.

## Lista de control por pantalla (pasarla antes de marcarla como hecha)
- [ ] Todas las funciones y datos del análisis de la pantalla están; nada inventado.
- [ ] Estados: contenido, carga, vacío, error, y los que apliquen (sin conexión, sin permiso, primer uso, contenido extremo).
- [ ] Cada comportamiento del código dibujado en secuencia con su disparador.
- [ ] Teléfono vertical y horizontal, tablet vertical y horizontal (adaptado, no estirado).
- [ ] Claro y oscuro, con contraste AA verificado.
- [ ] Inglés; texto largo (alemán) y RTL (árabe) en las pantallas con mucho texto; nada cortado.
- [ ] Áreas táctiles ≥ 48 dp, descripciones de accesibilidad y orden de foco anotados.
- [ ] Solo componentes y tokens del sistema de diseño.
- [ ] Textos con clave en `strings/en.json`; datos de ejemplo realistas.
- [ ] Se puede volver atrás; queda claro de qué flujo viene y adónde va.
