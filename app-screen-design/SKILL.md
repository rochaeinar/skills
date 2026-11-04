---
name: app-screen-design
description: Diseña las pantallas de una app móvil (Android por defecto) en Claude Design como un producto profesional, no como pantallas sueltas - primero analiza a fondo TODO el código (cada pantalla, clase, método, datos y comportamiento) o el texto que se le pase, piensa como PO qué mejoras reales y alcanzables permiten los datos existentes (nunca funciones imposibles), deja un archivo de preguntas y aclara todo con el usuario (paleta, ícono, alcance) y recién entonces trabaja solo durante horas diseñando el sistema de diseño y cada flujo en secuencia lógica, con todos los estados y comportamientos (diálogos, bottom sheets, snackbars, menús, deslizables), teléfono y tablet en vertical y horizontal, tema claro y oscuro, listo para 30 idiomas (inglés por defecto, RTL incluido). Úsalo cuando pidan "diseñar las pantallas", "rediseñar la app", "diseño de UI/UX", "mockups de la app", "pantallas en Claude Design", "diseña la app a partir de este texto / idea" o "rediseño completo".
---

# Diseño de pantallas de apps en Claude Design

Diseño de producto profesional y muy detallado: se entiende la app entera antes de dibujar nada, se aclara todo antes de empezar y después se trabaja de forma autónoma (horas, toda la noche) sin volver a preguntar.

**Regla de oro:** nada se diseña sin evidencia. Cada pantalla, dato, botón y mejora tiene que salir del código (con `archivo:línea`) o del texto del usuario. Si no hay evidencia, o es una pregunta para la fase 3, o se descarta.

Referencias del skill (leerlas en la fase donde se usan):
- `references/analisis-codigo.md`: cómo hacer la revisión profunda en Android (Compose/XML), Flutter, iOS y web.
- `references/ux-ui.md`: reglas de diseño, estados, comportamientos, tamaños de pantalla, accesibilidad y la lista de control por pantalla.
- `references/idiomas.md`: los 30 idiomas (códigos de Play y de Android), RTL, escrituras y textos largos.
- `templates/`: plantillas de los archivos de trabajo.
- `scripts/inventario.py`: inventario automático de archivos, pantallas, diálogos, rutas y fuentes de datos (es el punto de partida, **no** reemplaza leer el código).

## Carpeta de trabajo

Todo queda en `design/` en la raíz del proyecto (o la que el usuario indique; en modo texto, en la carpeta actual). Es el estado del skill: con ella se retoma un trabajo interrumpido.

| Archivo | Fase | Qué contiene |
|---|---|---|
| `cobertura.md` | 1 | Cada archivo fuente con su casilla: revisado o no. Al cerrar la fase 1 no queda ninguno sin revisar. |
| `analisis.md` | 1-2 | El negocio, los usuarios, el modelo de datos, cada pantalla, las funciones existentes y las mejoras propuestas. |
| `preguntas.md` | 3 | Todas las dudas, con opciones, recomendación y respuesta. |
| `decisiones.md` | 3-6 | Cada decisión tomada (del usuario o propia durante la ejecución) y su motivo. |
| `plan.md` | 4 | Sistema de diseño, mapa de flujos y orden de diseño de las pantallas. |
| `pantallas/<nn>-<id>.md` | 4-5 | La ficha de cada pantalla (`templates/pantalla.md`). |
| `progreso.md` | 5 | Lo hecho, lo que falta y los enlaces a los artefactos. Se actualiza después de cada pantalla. |
| `strings/en.json` (+ idiomas) | 5-6 | Catálogo de textos de la interfaz con claves. |
| `entrega.md` | 6 | Resumen final para el usuario y para quien programe. |

Si `design/` ya existe: leer `progreso.md` y `preguntas.md` y seguir desde donde quedó, sin repetir fases cerradas (salvo que el código haya cambiado: comparar con `git log` desde la fecha del análisis y revisar solo lo nuevo).

## Flujo de trabajo

### 0. Entrada y alcance
- **Con código** (por defecto si hay proyecto): la fuente de verdad es el código.
- **Con texto** (idea, especificación, notas, un `.md` o PDF): la fuente de verdad es el texto. Se analiza con el mismo rigor (fases 1 a 3 iguales: actores, entidades, reglas de negocio, flujos, datos), citando el párrafo en lugar de `archivo:línea`. Lo que el texto no dice es pregunta, no invento.
- **Con código y texto**: el texto dice qué cambiar o agregar; el código, lo que existe. Las contradicciones van a `preguntas.md`.
- **Plataforma:** Android (Material 3) salvo que se indique otra. iOS → Human Interface Guidelines; ambas → componentes adaptados a cada una donde difieran (navegación, diálogos, selectores).
- **Alcance:** por defecto la app completa. Si el usuario nombra pantallas o un flujo, igual se analiza la app entera (para la coherencia), pero solo se diseña lo pedido.

### 1. Revisión profunda (es una revisión profunda: sin atajos)
1. `python ~/.claude/skills/app-screen-design/scripts/inventario.py <raíz-del-proyecto> --out design/cobertura.md` genera la lista de **todos** los archivos fuente y lo que detecta en cada uno (pantallas, diálogos, sheets, toasts/snackbars, menús, rutas, permisos, entidades, DAO, red, preferencias).
2. Leer **cada archivo** de la lista, completo (con Read, en partes si es grande), y marcarlo en `cobertura.md` con una línea de lo que hace. Nada de "leí los nombres": cada clase y cada método. En un proyecto grande, ir por módulos y anotar en `analisis.md` a medida que se avanza (el contexto se resume solo; las notas no se pierden).
3. Para **cada pantalla** registrar en `analisis.md` (detalle en `references/analisis-codigo.md`): para qué sirve, cómo se llega y adónde lleva, qué datos muestra y de dónde salen (ViewModel → repositorio → Room/red/preferencias), cada acción del usuario y su resultado, cada estado (carga, vacío, error, sin permiso, sin conexión, contenido), cada comportamiento (diálogo, bottom sheet, menú, snackbar, toast, deslizar, arrastrar, pull-to-refresh, gestos, selección múltiple), validaciones, textos reales (`strings.xml`), permisos y casos borde.
4. Entender el negocio: qué problema resuelve la app, para quién, el modelo de datos completo (entidades, campos, relaciones), las reglas de negocio, la monetización (anuncios, compras), los servicios externos y las limitaciones técnicas (permisos, versión mínima de Android, sin conexión).
5. Anotar también la **deuda de UX** de la app actual: pantallas inconsistentes, estados sin manejar (p. ej. una lista sin estado vacío), errores que solo hacen `Log`, textos fijos en el código, accesibilidad que falta. Cada una es una mejora candidata.
6. Cierre de la fase: `cobertura.md` al 100 %. Si algo no se pudo leer (binario, generado, de terceros), anotarlo con el motivo.

### 2. Análisis de producto (pensar como PO)
- Lista de **funciones existentes**, cada una con su evidencia. El diseño las cubre todas: rediseñar no es quitar funciones (quitar una es una pregunta).
- **Mejoras propuestas**: solo las reales, alcanzables, útiles y funcionales. Cada una en `analisis.md` con: el problema del usuario que resuelve, **los datos o APIs que ya existen y la hacen posible** (entidad/campo/método), el esfuerzo estimado (S/M/L) y el valor. Ejemplos válidos: estadísticas o historial a partir de lo que ya se guarda, búsqueda y filtros sobre datos existentes, favoritos, ordenar, deshacer un borrado, accesos rápidos a lo más usado, un onboarding que explique permisos que la app ya pide.
- **Descartadas** (también se escriben, con el motivo): todo lo que exige datos que no se guardan ni se pueden calcular, IA/reconocimiento/servicios que la app no tiene, permisos que la plataforma no da, o un backend inexistente. "Sería lindo" no es motivo para diseñarlo.
- Priorizar con la regla del PO: primero lo que el usuario hace más seguido y lo que más falla hoy.

### 3. Preguntas y aclaraciones (todo se resuelve ANTES de diseñar)
1. Escribir `design/preguntas.md` con `templates/preguntas.md`: cada duda con contexto, opciones, la recomendada y su impacto. Siempre incluir:
   - **Paleta de colores**: si la app ya tiene (`colors.xml`, `Color.kt`, `themes.xml`), mostrarla y preguntar si se mantiene, se ajusta o se cambia; si no hay, pedirla o proponer 3 paletas armadas desde el ícono (con contraste verificado en claro y oscuro).
   - **Ícono de la app**: pedir la ruta (o confirmar el `ic_launcher` encontrado) y mirarlo con Read; es la base de la paleta y el tono. Sin ícono ni paleta, no se diseña.
   - Tono y personalidad de la marca, tipografía (si no hay, proponer), y si hay que respetar un diseño existente o es un rediseño libre.
   - Qué mejoras propuestas se aprueban (lista de la fase 2, todas con su recomendación).
   - Dudas de negocio o comportamiento que el código o el texto no aclaran (nunca suponer).
   - Contradicciones entre el texto y el código, funciones que parecen muertas o a medio hacer.
   - Alcance (todas las pantallas o algunas), plataforma, carpeta de salida, idiomas que se muestran en el diseño (ver `references/idiomas.md`).
2. Preguntar con `AskUserQuestion` (hasta 4 por vez, la recomendada primero) y, si son muchas, avisar que también se pueden responder editando `preguntas.md`. Anotar cada respuesta en `preguntas.md` y en `decisiones.md`.
3. Repetir hasta que no quede **ninguna** pregunta abierta. Si una respuesta abre otra duda, se pregunta ahora, no a mitad de la noche.
4. Antes de arrancar la ejecución autónoma, mostrar un resumen en pocas líneas: cuántas pantallas, flujos y mejoras entran, la paleta y la duración estimada. Desde aquí no se vuelve a preguntar.

### 4. Plan y sistema de diseño
- `plan.md`: **mapa de flujos** (diagrama de navegación con todas las pantallas, entradas y salidas; Mermaid), los flujos principales en orden de uso (primer uso → tarea principal → tareas secundarias → ajustes) y el orden en que se diseñan.
- **Sistema de diseño primero**, como primera parte del diseño en Claude Design: tokens de color (claro y oscuro, roles de Material 3, colores de estado, contraste ≥ 4.5:1 en texto), tipografía (escala, y una alternativa para escrituras no latinas), espaciado (rejilla de 4/8 dp), formas, elevación, íconos (un solo set), movimiento (duraciones y curvas) y los componentes que usa la app (botones, campos, tarjetas, listas, chips, barras, diálogos, sheets, snackbars, estados vacíos) con sus estados (normal, presionado, foco, deshabilitado, error). Todas las pantallas se arman con estos componentes.
- Una ficha por pantalla en `pantallas/` con `templates/pantalla.md`: objetivo, evidencia, datos, acciones, estados, comportamientos, textos y la secuencia de cuadros a dibujar.

### 5. Diseño en Claude Design (autónomo)
- Con la herramienta Artifact: `action: "quickstart"`, `intent: "design"`, y seguir las instrucciones del tipo Design que devuelve (crear el artefacto con su `type_url`, el sistema de diseño que ofrece o uno nuevo con los tokens del plan). Un artefacto para la app (sistema de diseño + flujos en orden); si son muchas pantallas, uno por flujo grande y un índice en `progreso.md`. Anotar cada URL en `progreso.md` al crearla.
- Diseñar **flujo por flujo, en el orden del plan**, como una historia: cada flujo empieza donde termina el anterior y se lee de izquierda a derecha con flechas y números de paso ("1 Toca ⋮ → 2 Menú → 3 Confirmar borrado → 4 Snackbar con Deshacer").
- Por cada pantalla, en este orden:
  1. El estado principal con datos reales y creíbles (sacados del modelo de datos, nunca "Lorem ipsum").
  2. **Todos los estados**: carga (skeleton), vacío (con acción), error (con reintento), sin conexión, sin permiso, primer uso, mucho contenido (textos largos, listas largas), según aplique.
  3. **Todos los comportamientos, en secuencia y entendibles**: cada diálogo, bottom sheet, menú, snackbar/toast, selector, validación de formulario, deslizable (antes / durante / después), selección múltiple, pull-to-refresh y transición, cada uno en su propio cuadro con el disparador anotado (qué toca el usuario) y el resultado. Ningún comportamiento del código se queda sin dibujar.
  4. **Variantes**: teléfono vertical (base, 360×800 dp), teléfono horizontal, tablet vertical y horizontal (tamaños de ventana compacto/medio/expandido: en tablet, dos paneles o rejilla, nunca el teléfono estirado), en **claro y oscuro**.
  5. **Idiomas**: en inglés; además, en las pantallas con más texto, una prueba de estrés en alemán (texto largo), árabe (RTL espejado) y una escritura compleja (hindi o birmano), según `references/idiomas.md`.
  6. Anotaciones para el desarrollo: medidas, componentes y tokens usados, claves de texto, accesibilidad (descripción para TalkBack, orden de foco) y movimiento.
- Al terminar cada pantalla: pasar la lista de control de `references/ux-ui.md`, agregar sus textos a `strings/en.json`, marcarla en `progreso.md` (con enlace) y seguir con la siguiente **sin esperar al usuario**.
- **Si surge una duda en la ejecución:** no detenerse. Tomar la opción más conservadora y coherente con lo ya decidido (nunca inventar una función), anotarla en `decisiones.md` como "decisión propia, revisar" y continuar. Solo se para ante un bloqueo real (sin acceso a la herramienta de diseño, por ejemplo) y se deja el motivo en `progreso.md`.
- Para trabajos largos: el usuario puede lanzarlo con `/loop` (sin intervalo) para que siga solo; cada vuelta retoma desde `progreso.md`.

### 6. Revisión final y entrega
- Revisión de coherencia de todo el conjunto: mismos componentes, espaciados, íconos y textos para lo mismo en todas las pantallas; navegación sin callejones sin salida (cada pantalla tiene cómo volver); cada función existente cubierta (comparar con la lista de la fase 2) y cada comportamiento del análisis dibujado.
- Pasar la matriz de cobertura: pantalla ↔ archivos de código ↔ funciones ↔ cuadros del diseño. Lo que falte se diseña ahora.
- Textos: `strings/en.json` completo; si se acordó en la fase 3, traducirlo a los 30 idiomas (traducción natural, no literal; marcar para revisión de un nativo los de menos recursos) y, si es Android, también como `values-<código>/strings.xml`.
- `entrega.md`: enlaces a los artefactos, lista de pantallas y flujos, mejoras incluidas (y descartadas con su motivo), decisiones propias a revisar, deuda de UX encontrada, y una guía de implementación (tokens a `Color.kt`/`Theme.kt` o `colors.xml`, componentes, orden sugerido de implementación).
- Mensaje final al usuario: corto, con los enlaces, el total de pantallas y cuadros, y las decisiones que tomó el skill solo y conviene revisar.

## Errores que hay que evitar
- Diseñar antes de leer todo el código o antes de cerrar las preguntas.
- Funciones imposibles o sin datos detrás (reconocimiento con IA, métricas que no se guardan, cuentas o servidores que no existen).
- Pantallas sueltas sin flujo, o comportamientos (diálogos, sheets, menús) que existen en el código y no aparecen en el diseño.
- Solo el estado "feliz": faltan carga, vacío, error y sin permiso.
- La versión de tablet como teléfono estirado; el horizontal sin pensar; el oscuro como un simple invertido.
- Textos de relleno, textos que no caben en alemán o un diseño que se rompe en RTL.
- Detenerse a preguntar durante la ejecución autónoma.
